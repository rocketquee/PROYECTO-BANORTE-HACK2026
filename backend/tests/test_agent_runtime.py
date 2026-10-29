"""Bounded model/tool orchestration and structured provider output tests."""
import asyncio

import pytest

from app.core import config
from app.schemas.api import ChatRequest
from app.services.agent import orchestrator as orch


def test_invalid_model_tool_is_retried_once(monkeypatch):
    class Provider:
        calls = 0

        async def chat_with_tools(self, *_args):
            self.calls += 1
            name = "not_allowed" if self.calls == 1 else "get_balance"
            return {
                "content": None,
                "tool_calls": [{"id": "call-1", "name": name, "arguments": "{}"}],
                "raw_message": {"role": "assistant"},
            }

    provider = Provider()
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "AGENT_RETRY_DELAY_SECONDS", 0)
    turn, _raw = asyncio.run(orch._request_provider_turn(
        provider, [], [], {"get_balance"}, "trace-test", 1,
    ))

    assert provider.calls == 2
    assert turn.tool_calls[0].name == "get_balance"


def test_provider_call_timeout_retries_once(monkeypatch):
    class Provider:
        calls = 0

        async def chat_with_tools(self, *_args):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.05)
            return {"content": "Listo", "tool_calls": [], "raw_message": {"role": "assistant"}}

    provider = Provider()
    monkeypatch.setattr(config, "AI_TIMEOUT_SECONDS", 0.005)
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "AGENT_RETRY_DELAY_SECONDS", 0)
    turn, _raw = asyncio.run(orch._request_provider_turn(
        provider, [], [], set(), "trace-test", 1,
    ))

    assert provider.calls == 2
    assert turn.content == "Listo"


def test_provider_invalid_output_fails_after_one_retry(monkeypatch):
    class Provider:
        calls = 0

        async def chat_with_tools(self, *_args):
            self.calls += 1
            return {
                "content": "Respuesta", "tool_calls": [],
                "raw_message": {"role": "assistant"}, "unexpected": "field",
            }

    provider = Provider()
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "AGENT_RETRY_DELAY_SECONDS", 0)

    with pytest.raises(orch.ProviderError):
        asyncio.run(orch._request_provider_turn(
            provider, [], [], set(), "trace-test", 1,
        ))
    assert provider.calls == 2


def test_read_tool_timeout_retries_within_limit(monkeypatch):
    class MCP:
        calls = 0

        async def call(self, _name, _arguments):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.05)
            return {"total_balance": 100}

    mcp = MCP()
    monkeypatch.setattr(orch, "mcp_client", mcp)
    monkeypatch.setattr(config, "AGENT_TOOL_TIMEOUT_SECONDS", 0.005)
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "AGENT_RETRY_DELAY_SECONDS", 0)
    result = asyncio.run(orch._call_mcp_tool(
        "get_balance", {}, "trace-test", 1, retryable=True,
    ))

    assert mcp.calls == 2
    assert result == {"total_balance": 100}


def test_live_tool_loop_stops_at_configured_step_limit(monkeypatch):
    class Provider:
        calls = 0

        async def chat_with_tools(self, *_args):
            self.calls += 1
            return {
                "content": None,
                "tool_calls": [{"id": f"call-{self.calls}", "name": "get_balance",
                                "arguments": "{}"}],
                "raw_message": {"role": "assistant", "content": None},
            }

        def assistant_message(self, out):
            return out["raw_message"]

        def tool_result_message(self, call, result):
            return {"role": "tool", "tool_call_id": call["id"], "content": "{}"}

    provider = Provider()
    async def fake_tool_call(_name, _arguments):
        return {"total_balance": 100}

    monkeypatch.setattr(orch, "get_provider", lambda: provider)
    monkeypatch.setattr(orch.mcp_client, "tool_specs", lambda: [
        {"name": "get_balance", "description": "Saldo", "input_schema": {"type": "object"}},
    ])
    monkeypatch.setattr(orch.mcp_client, "call", fake_tool_call)
    monkeypatch.setattr(config, "AGENT_MAX_STEPS", 2)
    monkeypatch.setattr(config, "AGENT_MAX_RETRIES", 0)
    monkeypatch.setattr(config, "AGENT_TOOL_TIMEOUT_SECONDS", 1)

    with pytest.raises(orch.ProviderError, match="límite de pasos"):
        asyncio.run(orch.live_response(ChatRequest(message="consulta mi saldo"), "trace-test"))
    assert provider.calls == 2
