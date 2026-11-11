"""Bucle ReAct: herramientas, límite de iteraciones y degradación a demo.

Todo corre con proveedores falsos y MCP falso: sin red y sin tocar la base real.
"""
import asyncio
import json

import pytest

import tools.finance_tools as ft
from app.core import config
from app.schemas.api import ChatRequest
from app.services.agent import loop, orchestrator as orch, providers
from app.services.mcp_catalog import MCP_ALLOWED_TOOLS

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_monthly_summary": ft.get_monthly_summary_impl,
    "analyze_spending": ft.analyze_spending_impl,
}


async def fake_call(name: str, args: dict) -> dict:
    return await IMPLS[name](**args)


@pytest.fixture(autouse=True)
def patched_agent(tmp_db, monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    specs = [
        {"name": name, "description": name,
         "input_schema": {"type": "object", "properties": {}}}
        for name in sorted(MCP_ALLOWED_TOOLS)
    ]
    monkeypatch.setattr(orch.mcp_client, "tool_specs", lambda: specs)
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 0)
    monkeypatch.setattr(config, "AGENT_RETRY_DELAY_SECONDS", 0)
    providers.reset_provider_health()
    orch.session_store.clear()
    yield
    providers.reset_provider_health()
    orch.session_store.clear()


class ScriptedProvider:
    """Proveedor falso: devuelve turnos en orden y registra cuántas veces se llamó."""

    name = "fake"
    model = "fake-deterministic"

    def __init__(self, turns: list[dict]) -> None:
        self.turns = list(turns)
        self.calls = 0

    async def chat_with_tools(self, _system, _messages, _tools):
        index = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        return self.turns[index]

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False)}


def _tool_turn(name: str, arguments: dict, call_id: str = "call-1") -> dict:
    return {
        "content": None,
        "tool_calls": [{"id": call_id, "name": name,
                        "arguments": json.dumps(arguments)}],
        "raw_message": {"role": "assistant", "content": None},
    }


def _text_turn(text: str) -> dict:
    return {"content": text, "tool_calls": [],
            "raw_message": {"role": "assistant", "content": text}}


def test_react_invokes_mcp_tool_and_returns_tool_calls(monkeypatch):
    provider = ScriptedProvider([
        _tool_turn("get_balance", {}),
        _text_turn("Revisa el resumen en pantalla."),
    ])
    monkeypatch.setattr(loop, "get_provider", lambda: provider)

    result = asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id="loop-1", mode="think"),
    ))

    assert result["mode"] == "think"
    assert result["degraded"] is False
    assert [call["name"] for call in result["tool_calls"]] == ["get_balance"]
    assert result["tool_calls"][0]["status"] == "ok"
    assert "get_balance" in result["tools_used"]
    assert result["provider"] == {
        "name": "fake", "model": "fake-deterministic",
        "latency_ms": result["provider"]["latency_ms"],
    }
    assert provider.calls == 2
    assert result["ui"] and result["ui"][0]["type"] == "financial_summary"


def test_react_stops_at_max_iterations_and_marks_degraded(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_ITERATIONS", 2)
    provider = ScriptedProvider([_tool_turn("get_balance", {})])
    monkeypatch.setattr(loop, "get_provider", lambda: provider)

    result = asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id="loop-2", mode="think"),
    ))

    assert provider.calls == 2
    assert result["degraded"] is True
    assert result["reason"] == "max_iterations"
    assert len(result["tool_calls"]) == 2


def test_provider_failure_degrades_to_demo_without_raising(monkeypatch):
    class BrokenProvider(ScriptedProvider):
        async def chat_with_tools(self, _system, _messages, _tools):
            self.calls += 1
            raise providers.ProviderError("proveedor caído")

    provider = BrokenProvider([])
    monkeypatch.setattr(loop, "get_provider", lambda: provider)

    result = asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id="loop-3", mode="think"),
    ))

    assert result["mode"] == "demo"
    assert result["degraded"] is True
    assert result["reason"] == "provider_unavailable"
    assert result["tool_calls"] == []
    assert result["reply"]


def test_missing_provider_degrades_with_not_configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "demo")
    monkeypatch.setattr(config, "AI_PROVIDER", "demo")
    providers.reset_provider_health()
    monkeypatch.setattr(loop, "get_provider", lambda: None)

    result = asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id="loop-4", mode="think"),
    ))

    assert result["mode"] == "demo"
    assert result["degraded"] is True
    assert result["reason"] == "not_configured"
    assert result["provider"]["name"] == "none"


def test_to_chat_response_preserves_react_contract(monkeypatch):
    provider = ScriptedProvider([
        _tool_turn("get_balance", {}),
        _text_turn("Listo."),
    ])
    monkeypatch.setattr(loop, "get_provider", lambda: provider)

    result = asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id="loop-5", mode="think"),
    ))
    response = loop.to_chat_response(result)

    assert response.mode == "think"
    assert response.reply == result["reply"]
    assert response.degraded is False
    assert response.tool_calls == result["tool_calls"]
    assert response.provider["name"] == "fake"
