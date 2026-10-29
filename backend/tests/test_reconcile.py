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


def test_reconcile_info_invariants_present(tmp_conn):
    with database.db() as conn:
        report = _report(conn)
    inv_map = {r["invariant"]: r for r in report["results"]}
    assert inv_map["INV-7"]["status"] == "info"
    assert inv_map["INV-8"]["status"] == "info"
    assert inv_map["INV-9"]["status"] == "info"
