"""Pruebas de reset de base (Tramo B)."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core import config, database, seed  # noqa: E402
from app.core.database import reset_database  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "reset.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    with database.db() as conn:
        seed.init_db(conn)
    return db_file


def test_reset_requires_confirm_or_dev_mode(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    with pytest.raises(PermissionError):
        reset_database(confirm=False)


def test_reset_works_with_confirm(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    report = reset_database(confirm=True)
    assert report["reset"] is True
    assert report["seeded"]["accounts"] > 0
    assert report["seeded"]["goals"] > 0
    assert report["seeded"]["transactions"] > 0
    assert report["migrations"] == "marked as fresh install"


def test_reset_is_deterministic(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    r1 = reset_database(confirm=True)
    r2 = reset_database(confirm=True)
    assert r1["seeded"] == r2["seeded"]


def test_reset_registers_migrations(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    reset_database(confirm=True)
    with database.db() as conn:
        versions = [
            r["version"]
            for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
    assert "ledger-v1" in versions
    assert "ledger-v2" in versions


def test_reset_endpoint_rejects_without_dev_mode(tmp_path, monkeypatch):
    """El endpoint /admin/reset debe fallar sin DEV_MODE (probado vía función)."""
    monkeypatch.setattr(config, "DEV_MODE", False)
    with pytest.raises(PermissionError):
        reset_database(confirm=False)
