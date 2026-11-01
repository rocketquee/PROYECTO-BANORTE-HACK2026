"""Reparación ledger-v3: plan sin escrituras y aplicación atómica con respaldo."""
import hashlib
import json
import sqlite3

import pytest

from app.core import ledger_repair, migrate, reconcile, seed
from app.services import finance


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger_snapshot(conn):
    """Estado que una apertura de meta no debe alterar."""
    return {
        "accounts": [
            (r["id"], r["balance_cents"])
            for r in conn.execute("SELECT id, balance_cents FROM accounts ORDER BY id")
        ],
        "goals_saved": [
            (r["id"], r["saved_amount_cents"])
            for r in conn.execute(
                "SELECT id, saved_amount_cents FROM savings_goals ORDER BY id"
            )
        ],
        "income_cents": conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE type='income'"
        ).fetchone()[0],
        "expense_cents": conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE type='expense'"
        ).fetchone()[0],
        "expense_rows": conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE type='expense'"
        ).fetchone()[0],
        "categories": [
            (r["category"], r["n"])
            for r in conn.execute(
                "SELECT category, COUNT(*) AS n FROM transactions"
                " WHERE category IS NOT NULL GROUP BY category ORDER BY category"
            )
        ],
        "available_cents": finance.accounts_balance_cents(conn),
        "total_cents": finance.total_balance_cents(conn),
    }


def _defective_db(path):
    """Replica el defecto real: fila 967 intercambiada y ahorro sin libro."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        seed.init_db(conn)
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.execute("DELETE FROM transfer_legs")
        conn.execute("DELETE FROM transactions")
        # La copia real termina en 967: las aperturas son 968 y 969.
        conn.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
        conn.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES ('transactions', 967)"
        )
        conn.executemany(
            "UPDATE savings_goals SET saved_amount_cents=? WHERE id=?",
            [(1_850_000, 1), (820_000, 2), (2_250_000, 3)],
        )
        conn.execute(
            "INSERT INTO transactions (id, date, description, amount_cents, type,"
            " category, account_id, goal_id, direction)"
            " VALUES (967,'2026-10-25','Movimiento 967',2250000,'transfer',"
            "NULL,3,2,'account_to_goal')"
        )
        conn.executescript(migrate.REGISTRY_DDL)
        conn.execute(
            "INSERT INTO schema_migrations (version, checksum, result_json)"
            " VALUES ('ledger-v1','checksum',?)",
            (json.dumps({"reclassified": [
                {"id": 967, "goal_id": 3, "amount": 22500.0}
            ]}),),
        )
        conn.commit()
    finally:
        conn.close()


def test_plan_is_read_only_and_reports_actions(tmp_path):
    db_file = tmp_path / "defective.db"
    _defective_db(db_file)
    before = _sha(db_file)

    report = ledger_repair.run(db_file, apply=False)

    assert _sha(db_file) == before
    assert report["swapped_rows"][0]["transaction_id"] == 967
    assert report["swapped_rows"][0]["restored_account_id"] == 2
    assert {c["action"] for c in report["opening_candidates"]} == {"opening_transfer"}
    assert {c["goal_id"] for c in report["opening_candidates"]} == {1, 2}


def test_apply_repairs_row_legs_and_openings(tmp_path):
    db_file = tmp_path / "defective.db"
    _defective_db(db_file)

    result = ledger_repair.run(db_file, apply=True, accept_openings=True)

    assert result["backup"]
    backup = db_file.parent / "backups" / result["backup"]
    assert backup.exists()
    assert backup.with_name(backup.name + ".sha256").exists()
    assert result["backup_sha256"] == _sha(backup)
    assert result["applied_swaps"] == [
        {"transaction_id": 967, "account_id": 2, "goal_id": 3}
    ]
    assert result["applied_legs"][0]["account_id"] == 2
    assert {o["goal_id"] for o in result["applied_openings"]} == {1, 2}

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT account_id, goal_id FROM transactions WHERE id=967"
        ).fetchone()
        assert (row["account_id"], row["goal_id"]) == (2, 3)
        leg = conn.execute(
            "SELECT account_id, amount_cents FROM transfer_legs"
            " WHERE transaction_id=967"
        ).fetchone()
        assert (leg["account_id"], leg["amount_cents"]) == (2, 2_250_000)
        openings = conn.execute(
            "SELECT goal_id, amount_cents FROM transactions"
            " WHERE description=?", (ledger_repair.OPENING_DESCRIPTION,)
        ).fetchall()
        assert {(r["goal_id"], r["amount_cents"]) for r in openings} == {
            (1, 1_850_000), (2, 820_000),
        }
        report = reconcile.reconcile(conn)
        assert report["ok"] is True, report["results"]
    finally:
        conn.close()


def test_openings_do_not_touch_accounts_income_expenses_categories_or_available(
    tmp_path,
):
    """Las aperturas 968/969 solo agregan libro de meta: el resto queda intacto."""
    db_file = tmp_path / "defective.db"
    _defective_db(db_file)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        before = _ledger_snapshot(conn)
        candidates = ledger_repair.plan(conn)["opening_candidates"]
        applied = ledger_repair._apply_openings(conn, candidates, "2026-11-01")
        conn.commit()
        after = _ledger_snapshot(conn)

        opening_ids = [o["transaction_id"] for o in applied]
        assert opening_ids == [968, 969]
        assert [o["goal_id"] for o in applied] == [1, 2]
        assert after["accounts"] == before["accounts"]
        assert after["goals_saved"] == before["goals_saved"]
        assert after["income_cents"] == before["income_cents"]
        assert after["expense_cents"] == before["expense_cents"]
        assert after["expense_rows"] == before["expense_rows"]
        assert after["categories"] == before["categories"]
        assert after["available_cents"] == before["available_cents"]
        assert after["total_cents"] == before["total_cents"]

        placeholders = ",".join("?" for _ in opening_ids)
        new_rows = conn.execute(
            "SELECT type, category, direction, amount_cents, goal_id"
            f" FROM transactions WHERE id IN ({placeholders}) ORDER BY id",
            opening_ids,
        ).fetchall()
        assert [(r["type"], r["category"], r["direction"])
                for r in new_rows] == [
            ("transfer", None, "account_to_goal"),
            ("transfer", None, "account_to_goal"),
        ]
        assert [r["amount_cents"] for r in new_rows] == [1_850_000, 820_000]
        assert [r["goal_id"] for r in new_rows] == [1, 2]
    finally:
        conn.close()


def test_apply_without_openings_keeps_ambiguity_visible(tmp_path):
    db_file = tmp_path / "defective.db"
    _defective_db(db_file)

    ledger_repair.run(db_file, apply=True, accept_openings=False)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        report = reconcile.reconcile(conn)
        item = {r["invariant"]: r for r in report["results"]}["goal_ledger"]
        assert item["status"] == "fail"
        assert {d["goal_id"] for d in item["details"]} == {1, 2}
        assert report["ok"] is False
    finally:
        conn.close()


def test_real_database_apply_is_blocked(tmp_path, monkeypatch):
    db_file = tmp_path / "real.db"
    _defective_db(db_file)
    monkeypatch.setattr(migrate, "DB_PATH", db_file)
    with pytest.raises(ledger_repair.RepairError, match="bloqueada"):
        ledger_repair.run(db_file, apply=True, accept_openings=True)


def test_real_database_apply_runs_only_with_explicit_authorization(
    tmp_path, monkeypatch
):
    db_file = tmp_path / "real.db"
    _defective_db(db_file)
    monkeypatch.setattr(migrate, "DB_PATH", db_file)

    result = ledger_repair.run(
        db_file, apply=True, accept_openings=True, allow_real=True
    )

    assert result["mode"] == "applied"
    assert result["backup_sha256"] == _sha(
        db_file.parent / "backups" / result["backup"]
    )
