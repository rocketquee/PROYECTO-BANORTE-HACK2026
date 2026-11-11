"""Paridad numérica demo vs think: la narrativa cambia, el dominio no."""
import asyncio
import json

import pytest

import tools.finance_tools as ft
from app.core import database
from app.core.seed import reference_today
from app.schemas.api import ChatRequest
from app.services import finance
from app.services.agent import composer, loop, orchestrator as orch
from app.services.mcp_catalog import MCP_ALLOWED_TOOLS

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_monthly_summary": ft.get_monthly_summary_impl,
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
    orch.session_store.clear()
    yield
    orch.session_store.clear()


class TwoStepProvider:
    """Primero consulta saldo y resumen; después narra sin calcular cifras."""

    name = "fake"
    model = "fake-deterministic"

    def __init__(self) -> None:
        self.calls = 0

    async def chat_with_tools(self, _system, _messages, _tools):
        self.calls += 1
        if self.calls == 1:
            today = reference_today()
            return {
                "content": None,
                "tool_calls": [
                    {"id": "call-1", "name": "get_balance", "arguments": "{}"},
                    {"id": "call-2", "name": "get_monthly_summary",
                     "arguments": json.dumps(
                         {"year": today.year, "month": today.month},
                     )},
                ],
                "raw_message": {"role": "assistant", "content": None},
            }
        return {
            "content": "Te dejo el resumen completo en pantalla.",
            "tool_calls": [],
            "raw_message": {"role": "assistant",
                            "content": "Te dejo el resumen completo en pantalla."},
        }

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False)}


def test_demo_and_think_share_the_same_domain_numbers(monkeypatch):
    request = ChatRequest(
        message="¿Cuál es mi saldo?", session_id="parity-1", mode="demo",
    )
    demo = asyncio.run(orch.demo_response(request, "trace-parity-demo"))

    provider = TwoStepProvider()
    monkeypatch.setattr(loop, "get_provider", lambda: provider)
    think_request = ChatRequest(
        message="¿Cuál es mi saldo?", session_id="parity-1", mode="think",
    )
    think = asyncio.run(loop.run_react(think_request, "trace-parity-think"))

    assert demo.mode == "demo"
    assert think["mode"] == "think"
    assert think["degraded"] is False

    demo_ui = [spec.model_dump() for spec in demo.ui]
    assert demo_ui == think["ui"]
    assert demo_ui[0]["type"] == "financial_summary"

    today = reference_today()
    with database.db() as conn:
        summary = finance.monthly_summary(conn, today.year, today.month)
        total_balance = finance.total_balance(conn)

    metrics = {metric["label"]: metric["value"] for metric in demo_ui[0]["metrics"]}
    assert metrics["Saldo total"] == composer.money(total_balance)
    assert metrics["Ingresos del mes"] == composer.money(summary["income"])
    assert metrics["Gastos del mes"] == composer.money(summary["expense"])

    # Solo la narrativa puede diferir: el dominio es la única autoridad.
    assert demo.message != think["reply"]
    assert think["ui"] == demo_ui
