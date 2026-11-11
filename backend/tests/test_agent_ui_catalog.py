"""Capa A2UI: catálogo estricto, planificador de dos fases y paridad demo/think.

Todo corre con MCP falso y proveedores falsos sobre una base temporal.
"""
import asyncio
import json

import pytest

import tools.finance_tools as ft
from app.core import config, database
from app.core.seed import reference_today
from app.schemas.api import ChatRequest
from app.schemas.ui import PendingAction
from app.services import finance
from app.services.agent import composer, loop, orchestrator as orch, ui_catalog
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
    monkeypatch.setattr(orch, "get_provider", lambda: None)
    monkeypatch.setattr(loop, "get_provider", lambda: None)
    orch.session_store.clear()
    yield
    orch.session_store.clear()


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


def _data_from(messages: list[dict]) -> dict:
    for message in reversed(messages):
        content = message.get("content") or ""
        if "DATOS DE HERRAMIENTAS" in content:
            return json.loads(content.split("\n", 1)[1])
    raise AssertionError("El planificador no recibió datos de herramientas.")


class ReasonerProvider:
    """Fase 1: consulta saldo y resume; no implementa el segundo paso."""

    name = "fake"
    model = "fake-deterministic"

    def __init__(self) -> None:
        self.turns = 0

    async def chat_with_tools(self, _system, _messages, _tools):
        self.turns += 1
        if self.turns == 1:
            return _tool_turn("get_balance", {})
        return _text_turn("Listo, revisa la pantalla.")

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False)}


class PlanningProvider(ReasonerProvider):
    """Fase 1 + fase 2 con planes controlados por la prueba."""

    def __init__(self, plans: list[str] | None = None) -> None:
        super().__init__()
        self.plans = list(plans or [])
        self.planner_calls = 0
        self.planner_messages: list[list[dict]] = []

    async def complete(self, _system, messages):
        self.planner_calls += 1
        self.planner_messages.append(messages)
        index = min(self.planner_calls - 1, len(self.plans) - 1)
        return self.plans[index]


class DataDrivenProvider(PlanningProvider):
    """Devuelve un plan construido con las cifras que recibe (sin inventar)."""

    async def complete(self, _system, messages):
        self.planner_calls += 1
        self.planner_messages.append(messages)
        return _stat_plan_from_data(messages)


def _stat_plan_from_data(messages: list[dict]) -> str:
    data = _data_from(messages)
    total = data["get_balance"]["total_balance"]
    return json.dumps({
        "title": "Tu saldo",
        "components": [{
            "type": "StatCard",
            "title": "Saldo total",
            "value": composer.money(total),
            "hint": "Datos de demostración",
        }],
    }, ensure_ascii=False)


def _run_think(monkeypatch, provider, session_id: str) -> dict:
    monkeypatch.setattr(loop, "get_provider", lambda: provider)
    return asyncio.run(loop.run_react(
        ChatRequest(message="¿Cuál es mi saldo?", session_id=session_id,
                    mode="think"),
    ))


# --------------------------------------------------------------- catálogo

def test_validate_ui_plan_rejects_component_outside_catalog():
    with pytest.raises(ui_catalog.UIPlanError) as exc:
        ui_catalog.validate_ui_plan({
            "title": "Pantalla",
            "components": [{"type": "Iframe", "src": "https://example.com"}],
        })
    assert "Iframe" in str(exc.value)


def test_validate_ui_plan_rejects_props_outside_catalog():
    with pytest.raises(ui_catalog.UIPlanError) as exc:
        ui_catalog.validate_ui_plan({
            "title": "Pantalla",
            "components": [{
                "type": "StatCard",
                "title": "Saldo",
                "value": "$1",
                "onClick": "alert(1)",
            }],
        })
    assert "onClick" in str(exc.value)


def test_validate_ui_plan_rejects_invented_numbers():
    with pytest.raises(ui_catalog.UIPlanError) as exc:
        ui_catalog.validate_ui_plan(
            {"title": "Pantalla", "components": [{
                "type": "StatCard", "title": "Saldo", "value": "$99,999",
            }]},
            tool_results={"get_balance": {"total_balance": 14800.0}},
        )
    assert "99999" in str(exc.value)


def test_transfer_form_uses_the_pending_amount():
    pending = PendingAction(
        id="pending-1",
        action="apply_savings_contribution",
        params={"amount": 500, "goal_name": "Viaje"},
        description="Abonar $500 a Viaje.",
    )
    plan = ui_catalog.build_ui_plan({}, pending=pending)

    component = plan.components[0]
    assert component.type == "TransferForm"
    assert component.amount == 500
    assert component.to_account == "Viaje"
    assert component.confirmation_text


# --------------------------------------------------------------- pipeline

def test_planner_builds_ui_plan_with_real_tool_numbers(monkeypatch):
    provider = DataDrivenProvider()
    result = _run_think(monkeypatch, provider, "ui-plan-real")

    with database.db() as conn:
        total_balance = finance.total_balance(conn)

    assert provider.planner_calls == 1
    assert result["ui_plan"]["title"] == "Tu saldo"
    assert result["ui_plan"]["components"][0] == {
        "type": "StatCard",
        "title": "Saldo total",
        "value": composer.money(total_balance),
        "hint": "Datos de demostración",
        "trend_pct": None,
        "tone": "neutral",
    }
    # El plan viaja en el sobre HTTP sin perder validación.
    response = loop.to_chat_response(result)
    assert response.ui_plan == result["ui_plan"]


def test_planner_repairs_invalid_plan_with_error_feedback(monkeypatch):
    provider = PlanningProvider([json.dumps({
        "title": "Rota",
        "components": [{"type": "UnknownCard", "title": "X"}],
    })])

    async def complete(_system, messages):
        provider.planner_calls += 1
        provider.planner_messages.append(messages)
        if provider.planner_calls == 1:
            return provider.plans[0]
        return _stat_plan_from_data(messages)

    monkeypatch.setattr(provider, "complete", complete)
    result = _run_think(monkeypatch, provider, "ui-plan-repair")

    assert provider.planner_calls == 2
    assert result["ui_plan"]["components"][0]["type"] == "StatCard"
    second_attempt = provider.planner_messages[1]
    feedback = [m["content"] for m in second_attempt
                if m["role"] == "user" and "rechazado" in m["content"]]
    assert feedback and "UnknownCard" in feedback[0]


def test_planner_falls_back_to_domain_data_after_repairs(monkeypatch):
    provider = PlanningProvider(["no es json", "tampoco"])
    result = _run_think(monkeypatch, provider, "ui-plan-fallback")

    with database.db() as conn:
        total_balance = finance.total_balance(conn)

    assert provider.planner_calls == 3  # intento inicial + 2 reparaciones
    values = [component.get("value")
              for component in result["ui_plan"]["components"]]
    assert composer.money(total_balance) in values


# --------------------------------------------------------------- paridad

class DemoParityProvider(ReasonerProvider):
    """Consulta saldo y resumen del mes; sin planificador LLM."""

    async def chat_with_tools(self, _system, _messages, _tools):
        self.turns += 1
        if self.turns == 1:
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
        return _text_turn("Te dejo el resumen en pantalla.")


def test_demo_and_think_ui_plans_share_the_same_numbers(monkeypatch):
    request = ChatRequest(
        message="¿Cuál es mi saldo?", session_id="ui-plan-parity", mode="demo",
    )
    demo = loop.attach_ui_plan(
        asyncio.run(orch.demo_response(request, "trace-ui-plan-demo")),
    )

    think = _run_think(monkeypatch, DemoParityProvider(), "ui-plan-parity")

    demo_values = {component["value"] for component in demo.ui_plan["components"]}
    think_values = {component["value"] for component in think["ui_plan"]["components"]}
    # El saldo total es el dato compartido por ambos caminos.
    with database.db() as conn:
        total_balance = finance.total_balance(conn)
    assert composer.money(total_balance) in demo_values
    assert composer.money(total_balance) in think_values


# --------------------------------------------------------------- endpoint

def test_agent_chat_route_backfills_ui_plan_for_demo(tmp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.schemas.ui import ChatResponse, FinancialSummarySpec, Metric

    monkeypatch.setattr(config, "AUTH_ENABLED", False)

    async def fake_handle(_body, force_demo=False):
        return ChatResponse(
            message="Listo.",
            mode="demo",
            ui=[FinancialSummarySpec(
                type="financial_summary",
                title="Tu resumen",
                metrics=[Metric(label="Saldo total", value="$14,800")],
            )],
        )

    monkeypatch.setattr(orch, "handle_chat", fake_handle)

    with TestClient(app) as client:
        response = client.post("/api/agent/chat", json={
            "message": "¿Cuál es mi saldo?",
            "session_id": "ui-plan-route",
            "mode": "demo",
        })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ui_plan"]["components"][0]["type"] == "StatCard"
    assert payload["ui_plan"]["components"][0]["value"] == "$14,800"
