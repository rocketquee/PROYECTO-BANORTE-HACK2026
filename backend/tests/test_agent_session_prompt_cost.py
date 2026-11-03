"""Fase B: sesión, prompt versionado, costo y orden de resolución."""
import asyncio
import logging

import pytest

from app.core import config
from app.schemas.api import ChatRequest, ConfirmRequest
from app.services.agent import orchestrator as orch
from app.services.agent import session_store
from app.services.agent.prompt_loader import (
    PromptBundle,
    PromptError,
    load_system_prompt,
)
from app.services.agent.providers import ProviderUsage


@pytest.fixture(autouse=True)
def clean_sessions():
    session_store.clear()
    yield
    session_store.clear()


def test_chat_requests_get_distinct_sessions_by_default():
    assert ChatRequest(message="hola").session_id != ChatRequest(message="hola").session_id
    assert ConfirmRequest(action_id="x").session_id is None


def test_session_state_isolated_between_conversations(monkeypatch):
    async def call_tool(name, _arguments):
        if name == "analyze_spending":
            return {
                "total": 40_000,
                "categories": [
                    {"category": "Comida", "amount": 40_000, "pct": 100, "count": 3},
                ],
            }
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    first = asyncio.run(orch.demo_response(
        ChatRequest(message="¿en qué gasté este mes?", session_id="session-a"),
    ))
    assert first.ui

    follow = asyncio.run(orch.demo_response(
        ChatRequest(message="y el mes pasado", session_id="session-a"),
    ))
    assert follow.ui

    isolated = asyncio.run(orch.demo_response(
        ChatRequest(message="y el mes pasado", session_id="session-b"),
    ))
    assert isolated.ui == []


def test_session_ttl_and_limit(monkeypatch):
    monkeypatch.setattr(session_store, "SESSION_TTL_SECONDS", 1)
    state = session_store.get_session("expired")
    state["_last_seen"] -= 2
    session_store.prune_sessions()
    assert session_store.get_existing_session("expired") is None

    monkeypatch.setattr(session_store, "MAX_SESSIONS", 2)
    session_store.get_session("one")
    session_store.get_session("two")
    session_store.get_session("three")
    assert session_store.get_existing_session("one") is None
    assert session_store.get_existing_session("three") is not None


def test_prompt_loader_reads_version_and_intents():
    bundle = load_system_prompt()
    assert isinstance(bundle, PromptBundle)
    assert bundle.version == "1.0.0"
    assert bundle.text.startswith("# Asistente financiero")
    assert "purchase_plan" in bundle.intent_sections
    assert "savings_contribution" in bundle.intent_sections
    assert orch.PROMPT_VERSION == bundle.version
    assert "calculate_credit_simulation" in orch._system_prompt_for("purchase_plan")


def test_prompt_loader_rejects_missing_and_malformed(tmp_path):
    with pytest.raises(PromptError):
        load_system_prompt(tmp_path / "missing.md")

    malformed = tmp_path / "prompt.md"
    malformed.write_text("# Sin versión\n\n## Rol y alcance\n", encoding="utf-8")
    with pytest.raises(PromptError):
        load_system_prompt(malformed)

    incomplete = tmp_path / "incomplete.md"
    incomplete.write_text(
        "<!-- version: 1.0.0 -->\n\n## Rol y alcance\nTexto\n", encoding="utf-8",
    )
    with pytest.raises(PromptError):
        load_system_prompt(incomplete)


def test_prompt_version_is_logged_in_trace(caplog):
    with caplog.at_level(logging.INFO, logger="banorte.agent"):
        asyncio.run(orch.handle_chat(
            ChatRequest(message="hola", session_id="trace-session"),
        ))
    records = [r for r in caplog.records if r.getMessage() == "agent_request_received"]
    assert records[-1].prompt_version == orch.PROMPT_VERSION


def test_cost_limit_stops_live_loop_and_missing_usage_does_not(monkeypatch):
    class Provider:
        model = "gpt-4o-mini"
        include_usage = True

        async def chat_with_tools(self, *_args):
            out = {
                "content": "Listo", "tool_calls": [],
                "raw_message": {"role": "assistant", "content": "Listo"},
            }
            if self.include_usage:
                out["usage"] = {"prompt_tokens": 10_000_000, "completion_tokens": 0}
            return out

    provider = Provider()
    monkeypatch.setattr(orch, "get_provider", lambda: provider)
    monkeypatch.setattr(orch.mcp_client, "tool_specs", lambda: [])
    monkeypatch.setattr(config, "AGENT_MAX_COST_USD", 0.01)

    with pytest.raises(orch.ProviderError, match="límite de costo"):
        asyncio.run(orch.live_response(
            ChatRequest(message="consulta mi saldo", session_id="cost-high"),
        ))

    provider.include_usage = False
    config.AGENT_MAX_COST_USD = 0
    response = asyncio.run(orch.live_response(
        ChatRequest(message="consulta mi saldo", session_id="cost-unknown"),
    ))
    assert response.mode == "live"


def test_estimate_cost_uses_provider_model(monkeypatch):
    monkeypatch.setattr(config, "AGENT_TOKEN_COSTS", {
        "test-model": {"input": 0.001, "output": 0.002},
    })

    class Provider:
        model = "test-model"

    usage = ProviderUsage(prompt_tokens=10, completion_tokens=20)
    assert orch._estimate_cost(usage, Provider()) == pytest.approx(0.05)


def test_goal_name_with_alert_word_resolves_entity():
    assert orch.detect_intent("abono a mi fondo de emergencia") == "savings_contribution"
    assert orch.detect_intent("crea una meta llamada Emergencia") == "savings"
    assert orch.detect_intent("estoy en peligro") == "emergency"
    assert orch.detect_intent("me estafaron") == "fraud"


def test_new_goal_requires_a_declared_name(monkeypatch):
    async def call_tool(name, _arguments):
        assert name == "get_savings_goals"
        return {"goals": []}

    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    response = asyncio.run(orch.demo_response(ChatRequest(
        message="ayúdame a ahorrar $5,000", session_id="no-name",
    )))
    assert response.pending_action is None
    assert "nombre" in response.message
    assert response.ui[0].type == "savings_goal_form"

    named = asyncio.run(orch.demo_response(ChatRequest(
        message="ayúdame a ahorrar $5,000 para un viaje", session_id="named",
    )))
    assert named.pending_action is not None
    assert named.pending_action.params["name"] == "Viaje"
