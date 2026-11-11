"""Memoria de correcciones en SQLite: registro, aislamiento y migración."""
import sqlite3

import pytest

from app.core import config, database, migrate, seed
from app.services.agent import loop, memory, providers


def test_record_correction_is_read_back_for_same_session(tmp_db):
    with database.db() as conn:
        memory.record_correction(
            conn,
            user_msg="Quiero ahorrar 5000 para un viaje",
            wrong_action="Crear una meta de 500,000",
            right_action="Crear una meta de 5,000",
            session_id="session-a",
        )
        rows = memory.recent_corrections(conn, "session-a", limit=5)

    assert len(rows) == 1
    assert rows[0]["kind"] == "correction"
    assert rows[0]["user_msg"] == "Quiero ahorrar 5000 para un viaje"
    assert rows[0]["right_action"] == "Crear una meta de 5,000"
    assert rows[0]["created_at"] == seed.reference_today().isoformat()


def test_corrections_do_not_leak_across_sessions(tmp_db):
    with database.db() as conn:
        memory.record_correction(
            conn, "corrige esto", "acción A", "acción B", session_id="session-a",
        )
        memory.record_correction(
            conn, "corrige aquello", "acción C", "acción D", session_id="session-b",
        )

        assert [row["right_action"] for row in
                memory.recent_corrections(conn, "session-a")] == ["acción B"]
        assert [row["right_action"] for row in
                memory.recent_corrections(conn, "session-b")] == ["acción D"]
        assert memory.recent_corrections(conn, "session-c") == []


def test_recent_corrections_respects_limit_and_order(tmp_db):
    with database.db() as conn:
        for index in range(3):
            memory.record_correction(
                conn, f"mensaje {index}", "mal", f"bien {index}", session_id="s",
            )
        rows = memory.recent_corrections(conn, "s", limit=2)

    assert [row["right_action"] for row in rows] == ["bien 2", "bien 1"]


def test_record_turn_and_counts(tmp_db):
    with database.db() as conn:
        memory.record_turn(
            conn, session_id="s", user_msg="hola", reply="¿En qué te ayudo?",
            tool_calls_json=[{"name": "get_balance", "status": "ok"}],
        )
        memory.record_correction(conn, "x", "mal", "bien", "s")
        counts = memory.counts(conn)
        row = conn.execute(
            "SELECT tool_calls_json FROM agent_memory WHERE kind = 'turn'"
        ).fetchone()

    assert counts == {"corrections": 1, "turns": 1}
    assert "get_balance" in row["tool_calls_json"]


def test_correction_enters_system_prompt_only_for_its_session(tmp_db):
    with database.db() as conn:
        memory.record_correction(
            conn,
            user_msg="Ahorra 5000, no 500000",
            wrong_action="Asumir 500,000",
            right_action="Usar 5,000",
            session_id="prompt-a",
        )

    prompt_a = loop.build_system_prompt("prompt-a")
    prompt_b = loop.build_system_prompt("prompt-b")

    assert "Usar 5,000" in prompt_a
    assert "Correcciones recientes del usuario" in prompt_a
    assert "Usar 5,000" not in prompt_b
    assert "Correcciones recientes del usuario" not in prompt_b


def test_memory_masks_pii_before_persisting(tmp_db):
    with database.db() as conn:
        memory.record_turn(
            conn, "s", "escribe a ana@example.com o al 5512345678",
            "respuesta", [{"name": "get_balance", "status": "ok"}],
        )
        row = conn.execute(
            "SELECT user_msg FROM agent_memory WHERE kind = 'turn'"
        ).fetchone()

    assert "ana@example.com" not in row["user_msg"]
    assert "5512345678" not in row["user_msg"]


def test_memory_reads_are_safe_before_migration(tmp_db):
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute("DROP TABLE agent_memory")
        conn.commit()
    finally:
        conn.close()

    with database.db() as db_conn:
        assert memory.recent_corrections(db_conn, "s") == []
        assert memory.counts(db_conn) == {"corrections": 0, "turns": 0}


def _drop_memory_version(db_file):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        migrate.mark_fresh_install(conn)
        conn.execute("DROP TABLE IF EXISTS agent_memory")
        conn.execute("DELETE FROM schema_migrations WHERE version = 'agent-memory-v1'")
        conn.commit()
    finally:
        conn.close()


def test_agent_memory_migration_aborts_without_verified_backup(tmp_db, monkeypatch):
    _drop_memory_version(tmp_db)
    missing = tmp_db.parent / "backups" / "no-existe.bak-20260101-000000"
    monkeypatch.setattr(migrate, "backup", lambda _db: missing)

    with pytest.raises(migrate.MigrationError):
        migrate.run_pending(tmp_db)

    conn = sqlite3.connect(tmp_db)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_memory'"
        ).fetchone()
    finally:
        conn.close()
    assert exists is None  # no se escribió nada sin respaldo verificado


def test_agent_memory_migration_applies_with_verified_backup(tmp_db):
    _drop_memory_version(tmp_db)

    report = migrate.run_pending(tmp_db)

    assert "agent-memory-v1" in report["pending"]
    assert report["applied"][0]["version"] == "agent-memory-v1"
    assert report["backup"]
    backup = tmp_db.parent / "backups" / report["backup"]
    assert backup.is_file()
    assert backup.with_name(backup.name + ".sha256").is_file()

    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(agent_memory)")}
        version = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = 'agent-memory-v1'"
        ).fetchone()
    finally:
        conn.close()
    assert {"id", "kind", "user_msg", "wrong_action", "right_action",
            "created_at", "session_id"} <= columns
    assert version is not None


def test_health_reports_agent_mode_and_memory(tmp_db, monkeypatch):
    from app.api import routes

    with database.db() as conn:
        migrate.mark_fresh_install(conn)
        memory.record_correction(conn, "x", "mal", "bien", "s")
        memory.record_turn(conn, "s", "hola", "respuesta", [])

    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    monkeypatch.setattr(config, "AI_PROVIDER", "demo")
    providers.reset_provider_health()

    data = routes.health()

    assert data["agent_mode"] == "demo"
    assert data["memory"] == {"corrections": 1, "turns": 1}
    assert "tools_supported" in data["provider"]
