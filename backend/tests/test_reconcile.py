"""Pruebas de reconciliación de invariantes (INV-1 a INV-9).

Las restricciones CHECK y UNIQUE de la base ya impiden insertar datos
inconsistentes (eso es correcto). Para verificar que la reconciliación los
detectaría si aparecieran, se usa `PRAGMA ignore_check_constraints = ON` en
las pruebas de INV-1 e INV-4. Para INV-5 (UNIQUE) se prueba la consulta de
detección directamente contra una tabla temporal sin restricción.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core import database, reconcile, seed  # noqa: E402


@pytest.fixture()
def tmp_conn(tmp_path, monkeypatch):
    db_file = tmp_path / "reconcile.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    with database.db() as conn:
        seed.init_db(conn)
    return db_file


def _report(conn):
    return reconcile.reconcile(conn)


def test_reconcile_passes_on_clean_db(tmp_conn):
    with database.db() as conn:
        report = _report(conn)
    assert report["ok"] is True
    assert report["failures"] == 0
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-1"]["status"] == "pass"
    assert inv_map["INV-4"]["status"] == "pass"
    assert inv_map["INV-5"]["status"] == "pass"
    assert inv_map["INV-6"]["status"] == "pass"
    assert inv_map["foreign_keys"]["status"] == "pass"


def test_reconcile_detects_bad_transaction_shape(tmp_conn):
    with database.db() as conn:
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute(
            "INSERT INTO transactions (date, description, amount_cents, type, category, account_id, goal_id, direction)"
            " VALUES ('2024-01-01','bad',1000,'transfer','Gastos',1,1,'account_to_goal')"
        )
        conn.commit()
        report = _report(conn)
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-1"]["status"] == "fail"
    assert inv_map["INV-1"]["rows_affected"] >= 1
    assert report["ok"] is False


def test_reconcile_detects_goal_over_cap(tmp_conn):
    with database.db() as conn:
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.execute(
            "UPDATE savings_goals SET saved_amount_cents = target_amount_cents + 1000 WHERE id=1"
        )
        conn.commit()
        report = _report(conn)
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-4"]["status"] == "fail"
    assert report["ok"] is False


def test_reconcile_detects_duplicate_idempotency_key(tmp_conn):
    # La tabla real tiene UNIQUE, por lo que probamos la consulta de
    # detección contra una tabla temporal sin esa restricción.
    with database.db() as conn:
        conn.execute(
            "CREATE TEMP TABLE tmp_idem (idempotency_key TEXT, action TEXT, request_hash TEXT, result_json TEXT)"
        )
        conn.execute(
            "INSERT INTO tmp_idem VALUES ('dup-key','apply_savings_goal','hash1','{}')"
        )
        conn.execute(
            "INSERT INTO tmp_idem VALUES ('dup-key','apply_savings_goal','hash1','{}')"
        )
        dupes = conn.execute(
            "SELECT COUNT(*) FROM ("
            " SELECT idempotency_key, COUNT(*) AS c"
            " FROM tmp_idem GROUP BY idempotency_key HAVING c > 1"
            ")"
        ).fetchone()[0]
    assert dupes == 1
    # Y en la tabla real no hay duplicados (UNIQUE lo impide).
    with database.db() as conn:
        report = _report(conn)
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-5"]["status"] == "pass"


def test_reconcile_reports_goal_ledger_difference_with_id_and_amount(tmp_conn):
    """INV-10: cada diferencia se reporta con meta, ahorrado, libro y monto."""
    with database.db() as conn:
        ledger = conn.execute(
            "SELECT COALESCE(SUM(CASE direction WHEN 'account_to_goal'"
            " THEN amount_cents ELSE -amount_cents END), 0)"
            " FROM transactions WHERE type='transfer' AND goal_id=1"
        ).fetchone()[0]
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.execute(
            "UPDATE savings_goals SET saved_amount_cents = ? WHERE id=1",
            (ledger + 12_345,),
        )
        conn.commit()
        report = _report(conn)
    item = {r["invariant"]: r for r in report["results"]}["goal_ledger"]
    assert item["status"] == "fail"
    assert item["rows_affected"] == 1
    detail = item["details"][0]
    assert detail["goal_id"] == 1
    assert detail["saved_cents"] == ledger + 12_345
    assert detail["ledger_cents"] == ledger
    assert detail["difference_cents"] == 12_345
    assert report["ok"] is False


def test_reconcile_detects_the_three_known_ledger_differences(tmp_conn):
    """Replica el defecto de la base real: +18,500, -14,300 y +22,500."""
    with database.db() as conn:
        conn.execute("DELETE FROM transactions WHERE type='transfer'")
        conn.execute(
            "INSERT INTO transactions (date, description, amount_cents, type,"
            " category, account_id, goal_id, direction)"
            " VALUES ('2026-10-25','Movimiento 967',2250000,'transfer',NULL,1,2,"
            "'account_to_goal')"
        )
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.executemany(
            "UPDATE savings_goals SET saved_amount_cents=? WHERE id=?",
            [(1_850_000, 1), (820_000, 2), (2_250_000, 3)],
        )
        conn.commit()
        report = _report(conn)
    item = {r["invariant"]: r for r in report["results"]}["goal_ledger"]
    assert item["status"] == "fail"
    diffs = {d["goal_id"]: d["difference_cents"] for d in item["details"]}
    assert diffs == {1: 1_850_000, 2: -1_430_000, 3: 2_250_000}
    assert report["ok"] is False


def test_reconcile_detects_completed_goal_without_target(tmp_conn):
    """INV-11: completada exige ahorrado igual al objetivo, y viceversa."""
    with database.db() as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.execute(
            "UPDATE savings_goals SET status='completada' WHERE id=1"
        )
        conn.commit()
        report = _report(conn)
        item = {r["invariant"]: r for r in report["results"]}["goal_status"]
        assert item["status"] == "fail"
        assert any(d["goal_id"] == 1 and d["status"] == "completada"
                   for d in item["details"])

        conn.execute(
            "UPDATE savings_goals SET status='activa',"
            " saved_amount_cents=target_amount_cents WHERE id=1"
        )
        conn.commit()
        report = _report(conn)
        item = {r["invariant"]: r for r in report["results"]}["goal_status"]
        assert item["status"] == "fail"
        assert any(d["goal_id"] == 1 and "objetivo alcanzado" in d["reason"]
                   for d in item["details"])


def test_reconcile_detects_orphan_transfer(tmp_conn):
    """INV-12: una transferencia sin meta existente no pasa inadvertida."""
    with database.db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT INTO transactions (date, description, amount_cents, type,"
            " category, account_id, goal_id, direction)"
            " VALUES ('2026-10-25','Transferencia huérfana',100000,'transfer',"
            "NULL,1,9999,'account_to_goal')"
        )
        conn.commit()
        report = _report(conn)
    item = {r["invariant"]: r for r in report["results"]}["orphan_transfers"]
    assert item["status"] == "fail"
    assert item["details"][0]["goal_id"] == 9999
    assert item["details"][0]["amount_cents"] == 100_000
    assert report["ok"] is False


def test_reconcile_detects_partial_debit_across_accounts(tmp_conn):
    """INV-13: un débito multi-cuenta debe registrar todas sus piernas."""
    from app.services import finance

    with database.db() as conn:
        amount = finance.accounts_balance(conn) - 0.01
        goal = finance.create_goal(conn, "Meta multi-cuenta", amount + 1_000)
        transfer = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=amount, direction="account_to_goal"
        )
        assert len(transfer["legs"]) >= 2, transfer["legs"]
        assert sum(leg["amount"] for leg in transfer["legs"]) == pytest.approx(
            transfer["amount"], abs=0.001)

        partial_leg = transfer["legs"][0]
        conn.execute(
            "UPDATE transfer_legs SET amount_cents = amount_cents - 1"
            " WHERE transaction_id=? AND account_id=?",
            (transfer["operation_id"], partial_leg["account_id"]),
        )
        conn.commit()
        report = _report(conn)
    item = {r["invariant"]: r for r in report["results"]}["transfer_legs"]
    assert item["status"] == "fail"
    assert item["details"][0]["transaction_id"] == transfer["operation_id"]
    assert item["details"][0]["difference_cents"] == 1
    assert report["ok"] is False


def test_reconcile_detects_all_injected_defects(tmp_conn):
    """Matriz: ahorro a mano, transferencia huérfana y débito parcial."""
    from app.services import finance

    with database.db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DROP TRIGGER IF EXISTS trg_goal_saved_bounds_upd")
        conn.execute("UPDATE savings_goals SET saved_amount_cents = 1 WHERE id=1")
        conn.execute(
            "INSERT INTO transactions (date, description, amount_cents, type,"
            " category, account_id, goal_id, direction)"
            " VALUES ('2026-10-25','Huérfana',50000,'transfer',NULL,1,9999,"
            "'account_to_goal')"
        )
        goal = finance.create_goal(conn, "Meta con pierna alterada", 5_000)
        transfer = finance.apply_transfer(
            conn, goal_id=goal["id"], amount=500, direction="account_to_goal"
        )
        conn.execute(
            "UPDATE transfer_legs SET amount_cents = amount_cents - 1"
            " WHERE transaction_id=?",
            (transfer["operation_id"],),
        )
        conn.commit()
        report = _report(conn)
    failed = {r["invariant"] for r in report["results"] if r["status"] == "fail"}
    assert {"goal_ledger", "orphan_transfers", "transfer_legs"} <= failed
    assert report["ok"] is False


def test_reconcile_info_invariants_present(tmp_conn):
    with database.db() as conn:
        report = _report(conn)
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-7"]["status"] == "info"
    assert inv_map["INV-8"]["status"] == "info"
    assert inv_map["INV-9"]["status"] == "info"
