"""Guardián de esquema en el arranque (Tramo B): la base debe estar en la
versión que el código espera y, si no, se migra o se niega a servir.

Cubre el requisito permanente de arranque:
- base de la versión anterior (REAL, sin `transfer`) → se migra al arrancar;
- base con registro de versiones desincronizado del esquema real → se niega a
  servir con un error claro (nunca se leen columnas inexistentes).
"""
import sqlite3

import pytest

from app.core import database, migrate
from app.core.migrate import MigrationError

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
def previous_version_base(tmp_path):
    """Base real con el esquema anterior a la versión esperada (REAL)."""
    path = tmp_path / "banorte.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute("INSERT INTO accounts (name, type, balance) VALUES ('Nómina','debit',24580.35)")
    conn.execute(
        "INSERT INTO transactions (date, description, amount, type, category, account_id)"
        " VALUES ('2026-10-15','Depósito de nómina',11000.37,'income','Ingresos',1)")
    conn.commit()
    conn.close()
    return path


def _mark_version(path, version: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(migrate.REGISTRY_DDL)
    conn.execute(
        "INSERT INTO schema_migrations (version, checksum, result_json, backup_file)"
        " VALUES (?,?,?,?)",
        (version, migrate._checksum(version), '{"mode": "manual"}', None),
    )
    conn.commit()
    conn.close()


def test_bootstraps_previous_version_base(tmp_path, monkeypatch, previous_version_base):
    """Arranque con una base de la versión anterior: migra y queda servible."""
    monkeypatch.setattr(database, "DB_PATH", previous_version_base)
    monkeypatch.setattr(database, "_initialized", False)
    database.ensure_database()  # no debe lanzar
    with database.db() as conn:
        assert migrate.current_version(conn) == migrate.CURRENT_SCHEMA_VERSION
        migrate.assert_schema_compatible(conn)


def test_boot_refuses_when_registry_drifts_from_schema(tmp_path, monkeypatch):
    """Registro en `ledger-v2` pero esquema REAL: se niega a servir (no se
    lee `amount`/`balance` inexistentes como si fueran `*_cents`)."""
    drifted = tmp_path / "banorte.db"
    conn = sqlite3.connect(drifted)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute("INSERT INTO accounts (name, type, balance) VALUES ('Nómina','debit',24580.35)")
    conn.commit()
    conn.close()
    _mark_version(drifted, "ledger-v2")

    monkeypatch.setattr(database, "DB_PATH", drifted)
    monkeypatch.setattr(database, "_initialized", False)
    with pytest.raises(MigrationError) as excinfo:
        database.ensure_database()
    assert "La base no está en la versión de esquema esperada" in str(excinfo.value)
