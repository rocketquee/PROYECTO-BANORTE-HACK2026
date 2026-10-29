"""SQLite access. Every operation opens a short-lived connection (prototype scale).
All queries are parameterized to prevent SQL injection."""
import sqlite3
from contextlib import contextmanager

from app.core import migrate, reconcile, seed
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


def _has_tables() -> bool:
    if not DB_PATH.exists():
        return False
    conn = connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        return count > 0
    finally:
        conn.close()


def ensure_database() -> None:
    """Prepara la base en el arranque, sin intervención (restricción de
    empaquetado): base nueva → siembra el esquema en la última versión y
    registra las migraciones como cubiertas; base existente → aplica las
    migraciones pendientes (con respaldo y transacción) y siembra solo si
    está vacía. Idempotente en cada arranque.
    """
    global _initialized
    if _initialized and DB_PATH.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _has_tables():
        with db() as conn:
            seed.init_db(conn)
            migrate.mark_fresh_install(conn)
    else:
        migrate.run_pending(DB_PATH)
        with db() as conn:
            seed.init_db(conn)  # siembra solo si no hay datos; no toca datos existentes
    _initialized = True


# Compatibilidad con llamadas existentes.
ensure_db = ensure_database


def reset_database(confirm: bool = False) -> dict:
    """Borra y vuelve a sembrar la base de forma controlada.

    Solo permitido en modo desarrollo (`DEV_MODE`) o cuando se pasa
    `confirm=True` explícitamente. Nunca disponible en producción sin
    protección.

    Flujo: borra tablas de usuario → `seed.init_db` (esquema + semilla
    determinista) → `migrate.mark_fresh_install` (migraciones registradas
    como cubiertas). Respetá el mismo flujo de arranque en fresco.
    """
    from app.core import config  # import local para evitar ciclo en pruebas

    if not (config.DEV_MODE or confirm):
        raise PermissionError(
            "El reset de base solo está permitido en DEV_MODE o con confirm=True."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')

        seed.init_db(conn)
        migrate.mark_fresh_install(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

        tx_count = conn.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]
        goal_count = conn.execute(
            "SELECT COUNT(*) FROM savings_goals"
        ).fetchone()[0]
        account_count = conn.execute(
            "SELECT COUNT(*) FROM accounts"
        ).fetchone()[0]

        return {
            "reset": True,
            "tables_dropped": len(tables),
            "tables": tables,
            "seeded": {
                "accounts": account_count,
                "goals": goal_count,
                "transactions": tx_count,
            },
            "migrations": "marked as fresh install",
        }
    finally:
        conn.close()


def reconcile_database() -> dict:
    """Ejecuta la reconciliación de invariantes sobre la base actual."""
    with db() as conn:
        return reconcile.reconcile(conn)
