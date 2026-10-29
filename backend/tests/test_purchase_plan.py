"""Purchase plan amount parsing, MCP composition, and UI event cycle."""
import asyncio
import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.api import ChatRequest, UIEventIn
from app.services import credit
from app.services.agent import orchestrator as orch


@pytest.mark.parametrize("prompt", [
    "¿Puedo comprar una PC de 45mil?",
    "¿Puedo comprar una PC de 45 mil?",
    "¿Puedo comprar una PC de $45,000?",
])
def test_purchase_amount_formats_and_intent(prompt):
    assert orch.detect_intent(prompt) == "purchase_plan"
    assert orch.extract_amount(prompt) == 45000


@pytest.mark.asyncio
async def test_purchase_plan_to_goal_uses_real_mcp_and_persists(tmp_db, monkeypatch):
    from app.services.mcp_client import MCPFinanceClient
    from httpx import ASGITransport, AsyncClient

    client = MCPFinanceClient()
    monkeypatch.setattr(orch, "mcp_client", client)
    await client.start()
    try:
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as api:
            plan_response = await api.post("/api/agent/chat", json={
                "message": "¿Puedo comprar una PC de 45 mil?",
            })
            assert plan_response.status_code == 200, plan_response.text
            plan = plan_response.json()
            assert plan["ui"][0]["type"] == "purchase_plan"

            selected_response = await api.post("/api/agent/chat", json={
                "message": "Quiero ahorrar para la compra",
                "ui_event": UIEventIn(
                    id="e2e-select-savings",
                    type="purchase_option_selected",
                    payload={"option_id": "savings_12"},
                    trace_id=plan["trace_id"],
                ).model_dump(),
            })
            assert selected_response.status_code == 200, selected_response.text
            selected = selected_response.json()
            assert selected["ui"][0]["selected_option_id"] == "savings_12"

            pending_response = await api.post("/api/agent/chat", json={
                "message": "Prepara la meta",
                "ui_event": UIEventIn(
                    id="e2e-request-goal",
                    type="purchase_goal_create_requested",
                    payload={"option_id": "savings_12"},
                    trace_id=plan["trace_id"],
                ).model_dump(),
            })
            assert pending_response.status_code == 200, pending_response.text
            pending = pending_response.json()
            assert pending["ui"][0]["goal_status"] == "confirm_required"

            confirmation_event = UIEventIn(
                id="e2e-confirm-goal",
                type="purchase_goal_confirmed",
                payload={
                    "option_id": "savings_12",
                    "confirmation_token": pending["ui"][0]["goal_confirmation_token"],
                    "idempotency_key": pending["ui"][0]["goal_idempotency_key"],
                },
                trace_id=plan["trace_id"],
            )
            confirm_response = await api.post("/api/agent/chat", json={
                "message": "Confirmo crear la meta",
                "ui_event": confirmation_event.model_dump(),
            })
            assert confirm_response.status_code == 200, confirm_response.text
            confirmed = confirm_response.json()
            assert confirmed["interaction_context"]["navigate"] == "ahorro"
            assert confirmed["ui"][0]["goal_status"] == "created"
            assert confirmed["ui"][1]["type"] == "savings_progress"
            assert any(
                goal["name"] == "Compra planeada"
                for goal in confirmed["ui"][1]["goals"]
            )

            replayed_response = await api.post("/api/agent/chat", json={
                "message": "Confirmo otra vez",
                "ui_event": UIEventIn(
                    id="e2e-second-confirm",
                    type="purchase_goal_confirmed",
                    payload={
                        "option_id": "savings_12",
                        "confirmation_token": pending["ui"][0]["goal_confirmation_token"],
                        "idempotency_key": pending["ui"][0]["goal_idempotency_key"],
                    },
                    trace_id=plan["trace_id"],
                ).model_dump(),
            })
            assert replayed_response.status_code == 200, replayed_response.text
            assert replayed_response.json() == confirmed

            goals_response = await api.get("/api/goals")
            assert goals_response.status_code == 200
            assert sum(
                goal["name"] == "Compra planeada"
                for goal in goals_response.json()["goals"]
            ) == 1

            persisted = await client.call("get_savings_goals", {})
            assert sum(goal["name"] == "Compra planeada" for goal in persisted["goals"]) == 1
    finally:
        await client.stop()


def test_purchase_intent_asks_for_amount_when_missing(monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "session", None)
    response = asyncio.run(orch.handle_chat(ChatRequest(message="¿Puedo comprar una PC?")))
    assert "¿Cuánto cuesta" in response.message
    assert response.ui == []


def test_purchase_amount_out_of_range_is_rejected_without_mcp(monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "session", None)
    response = asyncio.run(orch.handle_chat(ChatRequest(
        message="¿Puedo comprar una PC de $500?",
    )))
    assert "$1,000 a $10,000,000" in response.message
    assert response.ui == []


def _stub_purchase_tools(monkeypatch):
    async def call_tool(name, arguments):
        if name == "get_monthly_summary":
            today = date.today()
            return {"year": today.year, "month": today.month,
                    "income": 50000, "expense": 52000}
        if name == "get_balance":
            return {"total_balance": 100000}
        if name == "detect_recurring_charges":
            return {"monthly_total": 7250}
        if name == "calculate_credit_simulation":
            return credit.simulate_credit(
                arguments["amount"], arguments["months"], arguments["annual_rate"],
                arguments["method"],
            )
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "call", call_tool)


def test_purchase_plan_uses_mcp_results_and_computes_options(monkeypatch):
    _stub_purchase_tools(monkeypatch)
    trace_id = "purchase-plan-test"
    response = asyncio.run(orch._purchase_plan_response(45000, trace_id))

    spec = response.ui[0]
    assert spec.type == "purchase_plan"
    assert spec.current_balance == 100000
    assert spec.balance_after_cash_purchase == 55000
    assert spec.monthly_balance == -2000
    assert spec.fixed_payments_monthly == 7250
    assert [option.months for option in spec.options] == [None, 12, 12, 18, 24]
    assert spec.options[0].monthly_balance_after == -47000
    assert spec.options[1].monthly_balance_after == -5750
    assert spec.options[2].monthly_payment > 0
    assert "Ya gastaste $2,000 de más" in response.ui[0].title or \
        "Ya gastaste $2,000 de más" in response.message


def test_live_purchase_plan_uses_mcp_tools_and_returns_versioned_ui(monkeypatch):
    _stub_purchase_tools(monkeypatch)

    class Provider:
        calls = 0
        system_prompt = ""

        async def chat_with_tools(self, system, _messages, _specs):
            self.system_prompt = system
            self.calls += 1
            if self.calls == 1:
                tools = [
                    ("get_balance", {}),
                    ("get_monthly_summary", {
                        "year": date.today().year, "month": date.today().month,
                    }),
                    ("detect_recurring_charges", {}),
                    *[
                        ("calculate_credit_simulation", {
                            "amount": 45000, "months": term, "annual_rate": 15.9,
                            "method": "frances",
                        })
                        for term in (12, 18, 24)
                    ],
                ]
                calls = [
                    {"id": f"call-{index}", "name": name,
                     "arguments": json.dumps(arguments)}
                    for index, (name, arguments) in enumerate(tools)
                ]
                return {
                    "content": None, "tool_calls": calls,
                    "raw_message": {"role": "assistant", "content": "tool calls"},
                }
            return {
                "content": "Revisé las opciones.",
                "tool_calls": [],
                "raw_message": {"role": "assistant", "content": "Revisé las opciones."},
            }

        def assistant_message(self, out):
            return out["raw_message"]

        def tool_result_message(self, call, _result):
            return {"role": "tool", "tool_call_id": call["id"], "content": "{}"}

    provider = Provider()
    monkeypatch.setattr(orch, "get_provider", lambda: provider)
    monkeypatch.setattr(orch.mcp_client, "tool_specs", lambda: [
        {"name": name, "description": name, "input_schema": {"type": "object"}}
        for name in orch.MCP_ALLOWED_TOOLS
    ])
    response = asyncio.run(orch.live_response(
        ChatRequest(message="¿Puedo comprar una PC de 45mil?"),
        trace_id="live-purchase-plan",
    ))

    assert response.mode == "live"
    assert response.schema_version == "1.0"
    assert response.ui[0].type == "purchase_plan"
    assert len(response.ui[0].options) == 5
    assert "detect_recurring_charges" in response.tools_used
    assert provider.calls == 2
    assert "calculate_credit_simulation" in provider.system_prompt


def test_ui_event_selects_option_and_returns_updated_plan(monkeypatch):
    _stub_purchase_tools(monkeypatch)
    trace_id = "purchase-plan-event"
    asyncio.run(orch._purchase_plan_response(45000, trace_id))
    event = UIEventIn(
        id="event-123456",
        type="purchase_option_selected",
        payload={"option_id": "credit_18"},
        trace_id=trace_id,
    )
    response = asyncio.run(orch.handle_chat(ChatRequest(
        message="Elegí la opción de 18 meses",
        ui_event=event,
    )))

    assert response.mode == "demo"
    assert response.trace_id == trace_id
    assert response.ui[0].selected_option_id == "credit_18"
    assert "balance mensual estimado" in response.message


def test_replayed_ui_event_returns_same_response(monkeypatch):
    _stub_purchase_tools(monkeypatch)
    trace_id = "purchase-plan-replay"
    asyncio.run(orch._purchase_plan_response(45000, trace_id))
    event = UIEventIn(
        id="event-replay-123",
        type="purchase_option_selected",
        payload={"option_id": "cash"},
        trace_id=trace_id,
    )
    request = ChatRequest(message="Elegí contado", ui_event=event)
    first = asyncio.run(orch.handle_chat(request))
    replay = asyncio.run(orch.handle_chat(request))

    assert replay.model_dump() == first.model_dump()


def test_purchase_goal_requires_request_and_explicit_verified_confirmation(monkeypatch):
    now = date.today()
    generated = {"calls": 0, "goal": None, "arguments": None}

    async def call_tool(name, arguments):
        if name == "get_monthly_summary":
            return {"year": now.year, "month": now.month,
                    "income": 50000, "expense": 40000}
        if name == "get_balance":
            return {"total_balance": 100000}
        if name == "detect_recurring_charges":
            return {"monthly_total": 7250}
        if name == "calculate_credit_simulation":
            return credit.simulate_credit(
                arguments["amount"], arguments["months"], arguments["annual_rate"],
                arguments["method"],
            )
        if name == "create_savings_goal":
            generated["calls"] += 1
            generated["arguments"] = arguments
            generated["goal"] = {
                "id": 321, "name": arguments["name"],
                "target_amount": arguments["target_amount"], "saved_amount": 0,
                "progress_pct": 0, "deadline": arguments["deadline"], "status": "activa",
            }
            return {"status": "created", "goal": generated["goal"]}
        if name == "get_savings_goals":
            return {"goals": [generated["goal"]]}
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    trace_id = "purchase-goal-confirmation"
    asyncio.run(orch._purchase_plan_response(45000, trace_id))
    selected = UIEventIn(
        id="select-savings-option",
        type="purchase_option_selected",
        payload={"option_id": "savings_12"},
        trace_id=trace_id,
    )
    selected_response = asyncio.run(orch.handle_chat(ChatRequest(
        message="Elijo la meta de ahorro",
        ui_event=selected,
    )))
    assert selected_response.ui[0].selected_option_id == "savings_12"

    request = UIEventIn(
        id="request-savings-goal",
        type="purchase_goal_create_requested",
        payload={"option_id": "savings_12"},
        trace_id=trace_id,
    )
    pending = asyncio.run(orch.handle_chat(ChatRequest(
        message="Prepara la meta",
        ui_event=request,
    )))
    pending_spec = pending.ui[0]
    assert pending_spec.goal_status == "confirm_required"
    assert generated["calls"] == 0

    token = pending_spec.goal_confirmation_token
    key = pending_spec.goal_idempotency_key
    invalid_token = (token[:-1] + ("0" if token[-1] != "0" else "1"))
    rejected_confirmation = UIEventIn(
        id="reject-savings-confirmation",
        type="purchase_goal_confirmed",
        payload={
            "option_id": "savings_12",
            "confirmation_token": invalid_token,
            "idempotency_key": key,
        },
        trace_id=trace_id,
    )
    rejected = asyncio.run(orch.handle_chat(ChatRequest(
        message="Confirmo crear la meta",
        ui_event=rejected_confirmation,
    )))
    assert "No pude verificar" in rejected.message
    assert generated["calls"] == 0

    confirmation = UIEventIn(
        id="confirm-savings-goal",
        type="purchase_goal_confirmed",
        payload={
            "option_id": "savings_12",
            "confirmation_token": token,
            "idempotency_key": key,
        },
        trace_id=trace_id,
    )
    response = asyncio.run(orch.handle_chat(ChatRequest(
        message="Confirmo crear la meta",
        ui_event=confirmation,
    )))
    assert response.ui[0].goal_status == "created"
    assert response.ui[0].goal_created_id == 321
    assert response.ui[1].type == "savings_progress"
    assert response.interaction_context["navigate"] == "ahorro"
    assert generated["calls"] == 1
    assert generated["arguments"]["confirm"] is True
    assert generated["arguments"]["idempotency_key"] == key

    second_click = UIEventIn(
        id="confirm-savings-goal-again",
        type="purchase_goal_confirmed",
        payload={
            "option_id": "savings_12",
            "confirmation_token": token,
            "idempotency_key": key,
        },
        trace_id=trace_id,
    )
    replay = asyncio.run(orch.handle_chat(ChatRequest(
        message="Confirmo crear la meta",
        ui_event=second_click,
    )))
    assert replay.model_dump() == response.model_dump()
    assert generated["calls"] == 1


def test_goal_confirmation_event_requires_server_tokens():
    with pytest.raises(ValidationError):
        UIEventIn.model_validate({
            "id": "goal-confirm-no-token",
            "type": "purchase_goal_confirmed",
            "payload": {"option_id": "savings_12"},
            "trace_id": "purchase-plan-event",
        })


def test_ui_event_rejects_unknown_event_type():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({
            "message": "Evento inválido",
            "ui_event": {
                "id": "event-unknown",
                "type": "transfer_money",
                "payload": {"option_id": "cash"},
                "trace_id": "purchase-plan-event",
            },
        })


def test_stale_plan_event_returns_safe_message():
    event = UIEventIn(
        id="event-stale-123",
        type="purchase_option_selected",
        payload={"option_id": "cash"},
        trace_id="unknown-plan-trace",
    )
    response = asyncio.run(orch.handle_chat(ChatRequest(
        message="Elegí contado",
        ui_event=event,
    )))
    assert "ya no está disponible" in response.message
