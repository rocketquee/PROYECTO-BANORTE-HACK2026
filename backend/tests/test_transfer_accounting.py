import pytest

from app.core.database import db
from app.services import finance


def _goal(conn, target=1_000):
    return finance.create_goal(conn, "Meta de prueba", target)


def _transfers_cents(conn, goal_id):
    return conn.execute(
        "SELECT COALESCE(SUM(CASE direction"
        " WHEN 'account_to_goal' THEN amount_cents"
        " ELSE -amount_cents END), 0) FROM transactions"
        " WHERE type='transfer' AND goal_id=?",
        (goal_id,),
    ).fetchone()[0]


@pytest.mark.parametrize(("amount", "progress"), [(500, 50.0), (510, 51.0), (600, 60.0)])
def test_partial_contribution_stays_active_and_keeps_total_balance(
    tmp_db, amount, progress
):
    with db() as conn:
        goal = _goal(conn)
        total_before = finance.total_balance_cents(conn)
        accounts_before = finance.accounts_balance_cents(conn)

        result = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=amount, direction="account_to_goal"
        )

        assert result["goal"]["saved_amount"] == amount
        assert result["goal"]["progress_pct"] == progress
        assert result["goal"]["status"] == "activa"
        assert finance.accounts_balance_cents(conn) == accounts_before - amount * 100
        assert finance.total_balance_cents(conn) == total_before
        assert _transfers_cents(conn, goal["id"]) == amount * 100


def test_contribution_of_exact_remaining_completes_goal(tmp_db):
    with db() as conn:
        goal = _goal(conn)
        total_before = finance.total_balance_cents(conn)

        finance.apply_transfer(
            conn, goal_id=goal["id"], amount=500, direction="account_to_goal"
        )
        result = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=500, direction="account_to_goal"
        )

        assert result["goal"]["saved_amount"] == 1_000
        assert result["goal"]["progress_pct"] == 100.0
        assert result["goal"]["status"] == "completada"
        assert finance.total_balance_cents(conn) == total_before
        assert _transfers_cents(conn, goal["id"]) == 100_000


def test_withdrawal_reopens_completed_goal_and_preserves_total(tmp_db):
    with db() as conn:
        goal = _goal(conn)
        total_before = finance.total_balance_cents(conn)
        finance.apply_transfer(
            conn, goal_id=goal["id"], amount=1_000, direction="account_to_goal"
        )

        result = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=100, direction="goal_to_account"
        )

        assert result["goal"]["saved_amount"] == 900
        assert result["goal"]["progress_pct"] == 90.0
        assert result["goal"]["status"] == "activa"
        assert finance.total_balance_cents(conn) == total_before
        assert _transfers_cents(conn, goal["id"]) == 90_000


def test_multi_account_debit_records_every_leg(tmp_db):
    """INV-13: todas las cuentas debitadas quedan ligadas a la operación."""
    with db() as conn:
        balances_before = {
            r["id"]: r["balance_cents"]
            for r in conn.execute("SELECT id, balance_cents FROM accounts")
        }
        amount = finance.accounts_balance(conn) - 0.01
        goal = finance.create_goal(conn, "Meta multi-cuenta", amount + 1_000)

        result = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=amount, direction="account_to_goal"
        )

        legs = conn.execute(
            "SELECT account_id, amount_cents FROM transfer_legs"
            " WHERE transaction_id=? ORDER BY id",
            (result["operation_id"],),
        ).fetchall()
        assert len(legs) >= 2
        transaction_cents = conn.execute(
            "SELECT amount_cents FROM transactions WHERE id=?",
            (result["operation_id"],),
        ).fetchone()[0]
        assert sum(leg["amount_cents"] for leg in legs) == transaction_cents
        for leg in legs:
            assert conn.execute(
                "SELECT balance_cents FROM accounts WHERE id=?", (leg["account_id"],)
            ).fetchone()[0] == balances_before[leg["account_id"]] - leg["amount_cents"]
        assert result["goal"]["saved_amount"] == pytest.approx(amount, abs=0.001)


def test_seeded_goals_are_funded_by_the_ledger(tmp_db):
    """INV-10: el ahorro sembrado tiene una transferencia por cada centavo."""
    with db() as conn:
        rows = conn.execute(
            "SELECT g.id, g.saved_amount_cents,"
            " COALESCE(SUM(CASE t.direction WHEN 'account_to_goal'"
            " THEN t.amount_cents ELSE -t.amount_cents END), 0) AS ledger"
            " FROM savings_goals g LEFT JOIN transactions t"
            " ON t.goal_id=g.id AND t.type='transfer' GROUP BY g.id"
        ).fetchall()
        assert rows
        assert all(r["saved_amount_cents"] == r["ledger"] for r in rows)
        assert all(r["saved_amount_cents"] > 0 for r in rows)


def test_seed_is_deterministic_across_databases(tmp_path, monkeypatch):
    """Dos siembras producen exactamente el mismo contenido."""
    import hashlib
    import sqlite3

    from app.core import database, seed

    monkeypatch.delenv("BANORTE_DEMO_TODAY", raising=False)
    digests = []
    for index in range(2):
        db_file = tmp_path / f"seed-{index}.db"
        monkeypatch.setattr(database, "DB_PATH", db_file)
        with database.db() as conn:
            seed.init_db(conn)
        conn = sqlite3.connect(db_file)
        try:
            dump = "\n".join(conn.iterdump())
        finally:
            conn.close()
        digests.append(hashlib.sha256(dump.encode("utf-8")).hexdigest())
    assert digests[0] == digests[1]


def test_seeded_goal_funded_at_half_is_not_marked_complete(tmp_db):
    with db() as conn:
        row = conn.execute(
            "SELECT saved_amount_cents, target_amount_cents, status"
            " FROM savings_goals WHERE name='Enganche del auto'"
        ).fetchone()

        assert row["saved_amount_cents"] == 2_250_000
        assert row["target_amount_cents"] == 4_500_000
        assert row["status"] == "activa"


def test_api_can_apply_exact_remaining_contribution(tmp_db):
    import uuid

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        created = client.post(
            "/api/goals",
            json={"name": "Meta API", "target_amount": 1_000},
        )
        assert created.status_code == 201
        goal_id = created.json()["id"]

        for expected_saved in (500, 1_000):
            response = client.post(
                f"/api/goals/{goal_id}/transfers",
                json={
                    "amount": 500,
                    "direction": "account_to_goal",
                    "idempotency_key": str(uuid.uuid4()),
                },
            )
            assert response.status_code == 200, response.text
            goal = response.json()["goal"]
            assert goal["saved_amount"] == expected_saved

        assert goal["progress_pct"] == 100.0
        assert goal["status"] == "completada"
