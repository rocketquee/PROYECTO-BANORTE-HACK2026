import hashlib
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR / "mcp-server"))

from app.core import database  # noqa: E402
from app.core import seed as seed_mod  # noqa: E402


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Isolated SQLite database per test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    with database.db() as conn:
        seed_mod.init_db(conn)
    return db_file


@pytest.fixture(scope="session", autouse=True)
def guard_real_database_file():
    """Falla la sesión si alguna prueba escribe en la base real.

    La suite debe usar `tmp_db` para cualquier base de datos. Este guardián se
    instala antes de la primera prueba y compara el SHA-256 del archivo real al
    terminar; una migración accidental (como la que ocurrió al arrancar
    `TestClient` sin `tmp_db`) hace fallar la suite.
    """
    real_path = Path(database.DB_PATH)
    before = _sha256_file(real_path)
    yield
    after = _sha256_file(real_path)
    assert before == after, (
        "La suite modificó la base real "
        f"{real_path} (SHA-256 {before} → {after}). "
        "Usa el fixture `tmp_db` en cualquier prueba que arranque la app."
    )
