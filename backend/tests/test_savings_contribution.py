from datetime import date

import pytest

from app.core import config
from app.schemas.api import ChatRequest, UIEventIn
from app.services.agent import orchestrator as orch


@pytest.mark.parametrize(
    ("phrase", "remaining", "previous", "expected"),
    [
        ("quiero abonar todo lo que falta", 12_500, None, 12_500),
        ("quiero abonar el doble", 20_000, 1_250, 2_500),
        ("quiero abonar $750", 5_000, None, 750),
    ],
)
def test_local_fallback_understands_amount_references(
    phrase, remaining, previous, expected, monkeypatch,
):
    monkeypatch.setitem(orch._CTX, "last_contribution_amount", previous)
    monkeypatch.setitem(orch._CTX, "last_amount", None)
    assert orch._contribution_amount(phrase, remaining) == expected


@pytest.mark.asyncio
async def test_live_provider_selects_read_tools_and_never_writes_before_ui_confirmation(
    monkeypatch,
):
    class Provider:
        calls = 0
        observed_tools = []

        async def chat_with_tools(self, _system, _messages, tools):
            self.observed_tools = [tool["name"] for tool in tools]
            self.calls += 1
            next_tool = (
                ("get_savings_goals", "{}") if self.calls == 1 else
                ("get_balance", "{}") if self.calls == 2 else None
            )
            if next_tool:
                name, arguments = next_tool
                raw = {"role": "assistant", "content": None}
                return {
                    "content": None,
                    "tool_calls": [{
                        "id": f"call-{self.calls}", "name": name,
                        "arguments": arguments,
                    }],
                    "raw_message": raw,
                }
            return {
                "content": "Preparé una revisión.",
                "tool_calls": [],
                "raw_message": {"role": "assistant", "content": "Preparé una revisión."},
            }

        def assistant_message(self, raw):
            return raw

        def tool_result_message(self, _call, _result):
            return {"role": "tool", "content": "{}"}

    provider = Provider()
    goal = {
        "id": 906, "name": "Compra planeada", "target_amount": 10_000,
        "saved_amount": 2_000, "progress_pct": 20,
        "deadline": None, "status": "activa",
    }
    calls = []

    async def call_tool(name, arguments):
        calls.append(name)
        if name == "get_savings_goals":
            return {"goals": [goal]}
        if name == "get_balance":
            return {"total_balance": 20_000}
        raise AssertionError(f"LLM must not write before UI confirmation: {name}")

    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(orch, "get_provider", lambda: provider)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    monkeypatch.setattr(
        orch.mcp_client,
        "tool_specs",
        lambda: [
            {"name": name, "description": name, "input_schema": {"type": "object"}}
            for name in orch.MCP_ALLOWED_TOOLS
        ],
    )
    response = await orch.handle_chat(ChatRequest(
        message="abono a Compra planeada la mitad de lo que falta",
    ))

    assert response.mode == "live"
    assert response.ui[0].contribution_amount == 4_000
    assert {"get_savings_goals", "get_balance"} <= set(response.tools_used)
    assert "apply_savings_contribution" not in provider.observed_tools
    assert calls == ["get_savings_goals", "get_balance"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "saved", "expected"),
    [(10_000, 2_000, 4_000), (45_000, 15_000, 15_000), (1_500, 1_000, 250)],
)
async def test_half_of_remaining_contribution_calculates_and_waits_for_confirmation(
    monkeypatch, target, saved, expected,
):
    calls = []
    goal = {
        "id": 901, "name": "Compra planeada", "target_amount": target,
        "saved_amount": saved, "progress_pct": round(100 * saved / target, 1),
        "deadline": None, "status": "activa",
    }

    async def call_tool(name, arguments):
        calls.append(name)
        if name == "get_savings_goals":
            return {"goals": [goal]}
        if name == "get_balance":
            return {"total_balance": 50_000}
        if name == "apply_savings_contribution":
            raise AssertionError("No debe escribir antes del evento de confirmación")
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    response = await orch.handle_chat(ChatRequest(
        message="quiero hacer un abono a Compra planeada, la mitad de lo que falta",
    ))

    assert orch.detect_intent(
        "quiero hacer un abono a Compra planeada, la mitad de lo que falta"
    ) == "savings_contribution"
    assert response.ui[0].contribution_amount == expected
    assert response.ui[0].remaining_before == target - saved
    assert response.ui[0].remaining_after == target - saved - expected
    assert "Faltan" in response.message
    assert response.ui[0].confirmation_token
    assert "apply_savings_contribution" not in calls


@pytest.mark.asyncio
async def test_contribution_confirmation_is_verified_and_replay_does_not_duplicate(monkeypatch):
    calls = []
    before = {
        "id": 902, "name": "Compra planeada", "target_amount": 45_000,
        "saved_amount": 15_000, "progress_pct": 33.3,
        "deadline": None, "status": "activa",
    }
    after = {**before, "saved_amount": 30_000, "progress_pct": 66.7}

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        if name == "get_savings_goals":
            return {"goals": [before if not any(
                call[0] == "apply_savings_contribution" for call in calls
            ) else after]}
        if name == "get_balance":
            return {"total_balance": 50_000}
        if name == "apply_savings_contribution":
            return {
                "status": "applied", "goal": after, "amount": 15_000,
                "available_balance": 35_000,
            }
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    prepared = await orch.handle_chat(ChatRequest(
        message="abono a Compra planeada la mitad de lo que falta",
    ))
    spec = prepared.ui[0]
    assert not any(name == "apply_savings_contribution" for name, _ in calls)

    event = UIEventIn(
        id="confirm-contribution-1",
        type="savings_contribution_confirmed",
        payload={
            "goal_id": spec.goal_id,
            "amount": spec.contribution_amount,
            "confirmation_token": spec.confirmation_token,
            "idempotency_key": spec.idempotency_key,
        },
        trace_id=prepared.trace_id,
    )
    confirmed = await orch.handle_chat(ChatRequest(
        message="Confirmo el abono", ui_event=event,
    ))
    replay = await orch.handle_chat(ChatRequest(
        message="Doble clic", ui_event=event.model_copy(update={"id": "confirm-contribution-2"}),
    ))
    assert confirmed.ui[0].status == "completed"
    assert confirmed.ui[1].goals[0].saved_amount == 30_000
    assert replay.model_dump() == confirmed.model_dump()
    assert sum(name == "apply_savings_contribution" for name, _ in calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("balance", "amount", "message_part"),
    [
        (50_000, 30_001, "lo que falta"),
        (4_000, 5_000, "saldo disponible"),
    ],
)
async def test_contribution_above_limit_is_rejected_without_confirmation(
    monkeypatch, balance, amount, message_part,
):
    goal = {
        "id": 903, "name": "Compra planeada", "target_amount": 20_000,
        "saved_amount": 10_000, "progress_pct": 50,
        "deadline": None, "status": "activa",
    }
    calls = []

    async def call_tool(name, arguments):
        calls.append(name)
        if name == "get_savings_goals":
            return {"goals": [goal]}
        if name == "get_balance":
            return {"total_balance": balance}
        raise AssertionError(f"Unexpected write or tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    response = await orch.handle_chat(ChatRequest(
        message=f"abono a Compra planeada ${amount}",
    ))
    assert message_part in response.message
    assert response.ui == []
    assert "apply_savings_contribution" not in calls


@pytest.mark.asyncio
async def test_ambiguous_goal_reference_returns_selectable_goal_buttons(monkeypatch):
    goals = [
        {"id": 904, "name": "Viaje", "target_amount": 10_000, "saved_amount": 1_000,
         "progress_pct": 10, "deadline": None, "status": "activa"},
        {"id": 905, "name": "Viaje Europa", "target_amount": 25_000, "saved_amount": 2_000,
         "progress_pct": 8, "deadline": None, "status": "activa"},
    ]

    async def call_tool(name, arguments):
        if name == "get_savings_goals":
            return {"goals": goals}
        if name == "get_balance":
            return {"total_balance": 50_000}
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    response = await orch.handle_chat(ChatRequest(
        message="quiero hacer un abono a Viaje, la mitad de lo que falta",
    ))
    assert response.ui[0].status == "select_goal"
    assert {candidate.goal_id for candidate in response.ui[0].candidates} == {904, 905}
    selected = await orch.handle_chat(ChatRequest(
        message="La primera",
        ui_event=UIEventIn(
            id="choose-ambiguous-goal",
            type="savings_goal_selected",
            payload={"goal_id": 904},
            trace_id=response.trace_id,
        ),
    ))
    assert selected.ui[0].goal_id == 904
    assert selected.ui[0].contribution_amount == 4_500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_type"),
    [
        ("enséñame mi línea del tiempo de movimientos", "timeline"),
        ("enséñame mis estadísticas", "spending_chart"),
    ],
)
async def test_timeline_and_statistics_remain_in_chat_without_navigation(
    monkeypatch, tmp_db, message, expected_type,
):
    async def call_tool(name, arguments):
        if name == "get_transactions":
            return {"transactions": [{
                "id": 1, "date": date.today().isoformat(), "description": "Compra sintética",
                "amount": 100, "type": "expense", "category": "Comida",
            }], "total_count": 1}
        if name == "analyze_spending":
            return {"categories": [{
                "category": "Comida", "amount": 100, "pct": 100, "count": 1,
            }]}
        raise AssertionError(f"Unexpected tool: {name}")

    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    response = await orch.handle_chat(ChatRequest(message=message))
    assert response.ui[0].type == expected_type
    assert "navigate" not in response.interaction_context
