"""SQLite access. Every operation opens a short-lived connection (prototype scale).
All queries are parameterized to prevent SQL injection."""
import sqlite3
from contextlib import contextmanager

from app.core import seed
from app.core.config import DB_PATH, DATA_DIR

_initialized = False


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_db() -> None:
    """Create tables and seed synthetic data on first use."""
    global _initialized
    if _initialized and DB_PATH.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        seed.init_db(conn)
    _initialized = True
