"""Pruebas de la migración a centavos (D1, `ledger-v2`) y del runner versionado.

Cubre: base legacy REAL convertida con totales exactos al centavo,
idempotencia (segunda corrida no hace nada ni crea otro respaldo), respaldo
obligatorio, FK activas tras el rebuild, y triggers de INV operando en
centavos.
"""
import json
import sqlite3

import pytest

from app.core import migrate, seed


LEGACY_SCHEMA = """
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'MXN'
);
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, type TEXT NOT NULL, last4 TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    credit_limit REAL NOT NULL DEFAULT 0,
    closing_day INTEGER, due_day INTEGER
);
CREATE TABLE savings_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    saved_amount REAL NOT NULL DEFAULT 0,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'activa',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    type TEXT NOT NULL,
    category TEXT,
    account_id INTEGER REFERENCES accounts(id)
);
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL UNIQUE,
    monthly_limit REAL NOT NULL
);
CREATE TABLE idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture()
def legacy_db(tmp_path):
    """Base con el esquema REAL anterior a la Fase 1 (sin tipo `transfer`) y
    un gasto mal tipado vinculado a una meta por idempotencia."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(LEGACY_SCHEMA)
    conn.execute("INSERT INTO accounts (name, type, balance) VALUES ('Nómina','debit',24580.35)")
    conn.execute("INSERT INTO accounts (name, type, balance) VALUES ('Ahorro','savings',58200.0)")
    conn.execute(
        "INSERT INTO cards (name, type, last4, balance, credit_limit, closing_day, due_day)"
        " VALUES ('Principal','credit','4412',8450.5,30000.0,28,5)")
    # Base legacy: el ahorrado se escribía a mano (la tensión INV-4 que la
    # Fase 1 cerró); la migración lo respeta tal cual.
    conn.execute(
        "INSERT INTO savings_goals (name, target_amount, saved_amount, deadline)"
        " VALUES ('Meta',45000.0,22500.0,'2027-08-01')")
    conn.execute("INSERT INTO budgets (category, monthly_limit) VALUES ('Hogar',9000.0)")
    conn.execute("INSERT INTO budgets (category, monthly_limit) VALUES ('Super',6500.0)")
    conn.executemany(
        "INSERT INTO transactions (date, description, amount, type, category, account_id)"
        " VALUES (?,?,?,?,?,?)",
        [
            ("2026-10-15", "Depósito de nómina", 11000.37, "income", "Ingresos", 1),
            ("2026-10-03", "Renta departamento", 5500.0, "expense", "Hogar", 1),
            ("2026-10-14", "Soriana", 987.65, "expense", "Super", 2),
            # Gasto mal tipado: categoría fuera de la taxonomía y monto que
            # casa con el par (meta, monto) declarado por la idempotencia.
            ("2026-10-25", "Abono a meta: Meta", 22500.0, "expense", "Ahorro", 1),
        ],
    )
    conn.execute(
        "INSERT INTO idempotency_records (idempotency_key, action, request_hash, result_json)"
        " VALUES ('k-1','apply_savings_contribution','h','{\"goal\": {\"id\": 1},"
        " \"amount\": 22500.0}')")
    conn.commit()
    conn.close()
    return path


def _types(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1]: (r[2] or "").upper() for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_ledger_v2_converts_legacy_db_with_exact_totals(legacy_db, tmp_path):
    report = migrate.run_pending(legacy_db)

    versions = [a["version"] for a in report["applied"]]
    assert "ledger-v2" in versions
    assert report["backup"] and (legacy_db.parent / report["backup"]).exists()

    # Esquema: todas las columnas de dinero quedaron en centavos INTEGER.
    for table, columns in {
        "transactions": ["amount_cents"],
        "accounts": ["balance_cents"],
        "cards": ["balance_cents", "credit_limit_cents"],
        "savings_goals": ["target_amount_cents", "saved_amount_cents"],
        "budgets": ["monthly_limit_cents"],
    }.items():
        types = _types(legacy_db, table)
        for column in columns:
            assert types.get(column) == "INTEGER"

    conn = sqlite3.connect(legacy_db)
    conn.row_factory = sqlite3.Row
    try:
        # Totales exactos al centavo (los valores legacy en pesos × 100).
        assert conn.execute("SELECT SUM(amount_cents) FROM transactions"
                            " WHERE type='income'").fetchone()[0] == 1_100_037
        assert conn.execute("SELECT SUM(amount_cents) FROM transactions"
                            " WHERE type='expense'").fetchone()[0] == 648_765
        assert conn.execute("SELECT SUM(amount_cents) FROM transactions"
                            " WHERE type='transfer'").fetchone()[0] == 2_250_000
        assert conn.execute("SELECT SUM(balance_cents) FROM accounts").fetchone()[0] == 8_278_035
        assert conn.execute("SELECT monthly_limit_cents FROM budgets"
                            " WHERE category='Hogar'").fetchone()[0] == 900_000
        # Integridad referencial tras el rebuild.
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        # Los triggers en centavos están instalados y operan (INV-4 por motor).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO transactions (date, description, amount_cents, type, category,"
                " account_id, goal_id, direction)"
                " VALUES ('2026-10-26','Abono',900_000_000,'transfer',NULL,1,1,'account_to_goal')")
        conn.rollback()
    finally:
        conn.close()


def test_run_pending_is_idempotent(legacy_db):
    migrate.run_pending(legacy_db)
    first_backup = sorted(p.name for p in legacy_db.parent.glob("*.bak-*"))
    report = migrate.run_pending(legacy_db)
    assert report["pending"] == [] and report["applied"] == []
    assert sorted(p.name for p in legacy_db.parent.glob("*.bak-*")) == first_backup


def test_dry_run_writes_nothing(legacy_db):
    report = migrate.run_pending(legacy_db, dry_run=True)
    assert "ledger-v2" in report["pending"]
    assert "backup" not in report
    assert _types(legacy_db, "accounts")["balance"] == "REAL"  # intacta


def test_fresh_install_registers_all_versions(tmp_db, tmp_path):
    """Una base recién sembrada ya nace en centavos: las versiones se
    registran como cubiertas sin ejecutarse."""
    registry = tmp_path / "fresh.db"
    import shutil
    shutil.copy2(tmp_db, registry)
    conn = sqlite3.connect(registry)
    conn.row_factory = sqlite3.Row
    try:
        migrate.mark_fresh_install(conn)
        conn.commit()
        rows = {r["version"]: json.loads(r["result_json"])
                for r in conn.execute("SELECT * FROM schema_migrations")}
    finally:
        conn.close()
    assert set(rows) == {"ledger-v1", "ledger-v2"}
    assert all(r.get("mode") == "fresh_install" for r in rows.values())
    # Y el runner no encuentra nada pendiente sobre esa base.
    report = migrate.run_pending(registry)
    assert report["pending"] == []


def test_seed_schema_matches_migration_target():
    """Fuente única: el DDL que siembra y el que usa la migración son el mismo."""
    assert "amount_cents INTEGER" in seed.TABLE_DDL["transactions"]
    assert "balance_cents INTEGER" in seed.TABLE_DDL["accounts"]
