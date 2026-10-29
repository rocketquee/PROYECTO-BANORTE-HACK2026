import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR / "mcp-server"))

from app.core import database  # noqa: E402
from app.core import seed as seed_mod  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Isolated SQLite database per test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    with database.db() as conn:
        seed_mod.init_db(conn)
    return db_file
