"""Guardia: arrancar la app en pruebas nunca debe tocar `banorte.db` real."""
import hashlib
from pathlib import Path

from app.core import config, database, migrate


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_testclient_startup_uses_tmp_database(tmp_db):
    """El lifespan de la app migra/verifica la base temporal, no la real."""
    real_path = Path(config.DB_PATH)
    before = _sha256_file(real_path)

    with database.db() as conn:
        migrate.mark_fresh_install(conn)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert database.DB_PATH == tmp_db
    assert _sha256_file(real_path) == before
