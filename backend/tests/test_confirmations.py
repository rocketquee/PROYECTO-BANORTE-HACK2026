"""Confirmaciones persistentes: TTL, sesión, principal, replay y concurrencia."""
import asyncio
import hashlib
import sqlite3
import time

import pytest

from app.schemas.api import ChatRequest
from app.schemas.ui import PendingAction
from app.services.agent import confirmations, orchestrator as orch, session_store


def _action(action_id: str = "pa_" + "x" * 32) -> PendingAction:
    return PendingAction(
        id=action_id,
        action="create_savings_goal",
        params={"name": "Viaje", "target_amount": 5_000, "deadline": "2027-10-30"},
        description="Crear meta",
    )


def _row(db_path, action_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM pending_confirmations WHERE token_hash=?",
            (hashlib.sha256(action_id.encode("utf-8")).hexdigest(),),
        ).fetchone()
    finally:
        conn.close()


def test_register_stores_hash_and_binding(tmp_db):
    action = _action()
    confirmations.register(
        action, session_id="session-a", trace_id="trace-a", principal_id="admin",
    )

    row = _row(tmp_db, action.id)
    assert row is not None
    assert row["token_hash"] != action.id
    assert row["session_id"] == "session-a"
    assert row["principal_id"] == "admin"
    assert row["trace_id"] == "trace-a"
    assert row["expires_at"] > int(time.time())
    assert row["consumed_at"] is None
    assert row["result_json"] is None


def test_claim_rejects_other_session_and_principal(tmp_db):
    action = _action()
    confirmations.register(action, session_id="session-a", principal_id="admin")

    with pytest.raises(confirmations.ConfirmationError):
        confirmations.claim(action.id, session_id="session-b", principal_id="admin")
    with pytest.raises(confirmations.ConfirmationError):
        confirmations.claim(action.id, session_id="session-a", principal_id="other")

    claim = confirmations.claim(action.id, session_id="session-a", principal_id="admin")
    assert claim.action == "create_savings_goal"
    assert claim.params["idempotency_key"]


def test_claim_is_one_time_and_replay_returns_cached_result(tmp_db):
    action = _action()
    confirmations.register(action, session_id="session-a", principal_id="local")

    first = confirmations.claim(action.id, session_id="session-a")
    assert first.replay is None
    with pytest.raises(confirmations.ConfirmationError):
        confirmations.claim(action.id, session_id="session-a")

    result = {"status": "created", "goal": {"id": 7, "name": "Viaje"}}
    confirmations.finish(action.id, result)
    replay = confirmations.claim(action.id, session_id="session-a")
    assert replay.replay == result


def test_release_allows_retry_after_tool_failure(tmp_db):
    action = _action()
    confirmations.register(action, session_id="session-a", principal_id="local")

    assert confirmations.claim(action.id, session_id="session-a").replay is None
    confirmations.release(action.id)
    assert confirmations.claim(action.id, session_id="session-a").replay is None


def test_expired_confirmation_is_rejected(tmp_db):
    action = _action()
    confirmations.register(action, session_id="session-a", principal_id="local")
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute(
            "UPDATE pending_confirmations SET expires_at=? WHERE token_hash=?",
            (int(time.time()) - 1,
             hashlib.sha256(action.id.encode("utf-8")).hexdigest()),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(confirmations.ConfirmationError) as excinfo:
        confirmations.claim(action.id, session_id="session-a")
    assert excinfo.value.status_code == 410


def test_execute_pending_calls_tool_once_and_replays(tmp_db, monkeypatch):
    calls = []

    async def fake_call(name, args):
        calls.append((name, args))
        return {"status": "created", "goal": {"id": 7, "name": "Viaje"}}

    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    action = _action()
    orch.register_pending(action, {"session_id": "session-a"}, trace_id="trace-a")

    first = asyncio.run(orch.execute_pending(action.id, "session-a"))
    second = asyncio.run(orch.execute_pending(action.id, "session-a"))

    assert first == second
    assert first["action"] == "create_savings_goal"
    assert len(calls) == 1
    assert calls[0][0] == "create_savings_goal"
    assert calls[0][1]["confirm"] is True
    assert calls[0][1]["idempotency_key"]


def test_execute_pending_rejects_other_session(tmp_db, monkeypatch):
    async def fake_call(_name, _args):
        raise AssertionError("No debe ejecutarse con otra sesión")

    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    action = _action()
    orch.register_pending(action, {"session_id": "session-a"})

    with pytest.raises(confirmations.ConfirmationError):
        asyncio.run(orch.execute_pending(action.id, "session-b"))


def test_confirm_route_maps_confirmation_error(monkeypatch):
    from fastapi import HTTPException

    from app.api import routes
    from app.schemas.api import ConfirmRequest

    async def fail(*_args, **_kwargs):
        raise confirmations.ConfirmationError("expirada", status_code=410)

    monkeypatch.setattr(routes.orchestrator, "execute_pending", fail)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(routes.agent_confirm(ConfirmRequest(
            action_id="pa_" + "x" * 32, session_id="session-a",
        )))
    assert excinfo.value.status_code == 410


def test_demo_pending_action_is_persisted(tmp_db, monkeypatch):
    async def fake_call(_name, _args):
        return {"goals": []}

    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    session = session_store.get_session("session-a")
    response = asyncio.run(orch.demo_response(
        ChatRequest(message="ayúdame a ahorrar $5,000 para un viaje",
                    session_id="session-a"),
        "trace-demo", session,
    ))

    assert response.pending_action is not None
    row = _row(tmp_db, response.pending_action.id)
    assert row is not None
    assert row["session_id"] == "session-a"
    assert row["trace_id"] == "trace-demo"
