"""Fase C: fundamentación de cifras, `sin_dato` y minimización de resultados."""
import asyncio
import json

import pytest

from app.schemas.api import ChatRequest
from app.services.agent import orchestrator as orch


class ScriptedProvider:
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0
        self.tool_results = []

    async def chat_with_tools(self, _system, _messages, _tools):
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        return turn

    def assistant_message(self, raw):
        return raw

    def tool_result_message(self, call, result):
        self.tool_results.append(result)
        return {
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps(result, ensure_ascii=False),
        }


def _tool_turn(name="get_balance"):
    return {
        "content": None,
        "tool_calls": [{"id": "call-1", "name": name, "arguments": "{}"}],
        "raw_message": {"role": "assistant", "content": None},
    }


def _text_turn(text):
    return {
        "content": text,
        "tool_calls": [],
        "raw_message": {"role": "assistant", "content": text},
    }


def _run_live(monkeypatch, provider, tool_result, tool_name="get_balance"):
    async def call_tool(name, _arguments):
        assert name == tool_name
        return tool_result

    monkeypatch.setattr(orch, "get_provider", lambda: provider)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch.mcp_client, "call", call_tool)
    monkeypatch.setattr(
        orch.mcp_client,
        "tool_specs",
        lambda: [{
            "name": tool_name,
            "description": tool_name,
            "input_schema": {"type": "object"},
        }],
    )
    return asyncio.run(orch.live_response(
        ChatRequest(message="consulta mi saldo"), "trace-grounding",
    ))


def test_grounding_accepts_tool_figure_without_retry(monkeypatch):
    provider = ScriptedProvider([
        _tool_turn(),
        _text_turn("Tu saldo es $20,000."),
    ])
    response = _run_live(monkeypatch, provider, {"total_balance": 20_000})

    assert response.message == "Tu saldo es $20,000."
    assert provider.calls == 2


def test_grounding_blocks_invented_figure_after_one_retry(monkeypatch):
    provider = ScriptedProvider([
        _tool_turn(),
        _text_turn("Tu saldo es $999,999."),
        _text_turn("Tu saldo es $20,000."),
    ])
    response = _run_live(monkeypatch, provider, {"total_balance": 20_000})

    assert response.message == "Tu saldo es $20,000."
    assert "999" not in response.message
    assert provider.calls == 3


def test_grounding_falls_back_when_retry_keeps_inventing(monkeypatch):
    tool_result = {"total_balance": 20_000}
    provider = ScriptedProvider([
        _tool_turn(),
        _text_turn("Tu saldo es $999,999."),
        _text_turn("Tu saldo es $888,888."),
    ])
    response = _run_live(monkeypatch, provider, tool_result)

    assert response.message == orch._grounding_fallback(tool_result)
    assert "999" not in response.message
    assert "888" not in response.message
    assert provider.calls == 3


def test_sin_dato_replaces_zero_figure(monkeypatch):
    tool_result = {
        "transactions": [],
        "total_count": 0,
        "sin_dato": {
            "code": "transactions_empty",
            "message": "No hay movimientos para los filtros solicitados.",
            "period": None,
        },
    }
    provider = ScriptedProvider([
        _tool_turn("get_transactions"),
        _text_turn("Encontré 0 movimientos y el total fue $0."),
    ])
    response = _run_live(
        monkeypatch, provider, tool_result, tool_name="get_transactions",
    )

    assert response.message == "No hay movimientos para los filtros solicitados."
    assert "$0" not in response.message
    assert provider.calls == 2


def test_sin_dato_keeps_explicit_empty_message(monkeypatch):
    tool_result = {
        "transactions": [],
        "total_count": 0,
        "sin_dato": {
            "code": "transactions_empty",
            "message": "No hay movimientos para los filtros solicitados.",
            "period": None,
        },
    }
    provider = ScriptedProvider([
        _tool_turn("get_transactions"),
        _text_turn("No hay movimientos para los filtros solicitados."),
    ])
    response = _run_live(
        monkeypatch, provider, tool_result, tool_name="get_transactions",
    )

    assert response.message == "No hay movimientos para los filtros solicitados."
    assert provider.calls == 2


def test_absent_sin_dato_allows_real_zero(monkeypatch):
    provider = ScriptedProvider([
        _tool_turn(),
        _text_turn("Tu saldo es $0."),
    ])
    response = _run_live(monkeypatch, provider, {"total_balance": 0})

    assert response.message == "Tu saldo es $0."
    assert provider.calls == 2


def test_tool_result_is_masked_before_model(monkeypatch):
    tool_result = {
        "total_balance": 20_000,
        "customer": {"name": "Ana Pérez", "email": "ana@example.com"},
        "number": 4111111111111111,
        "note": "NIP 9876",
    }
    provider = ScriptedProvider([
        _tool_turn(),
        _text_turn("Listo."),
    ])
    _run_live(monkeypatch, provider, tool_result)

    sent = json.dumps(provider.tool_results[0], ensure_ascii=False)
    assert "Ana" not in sent
    assert "ana@example.com" not in sent
    assert "9876" not in sent
    assert "4111111111111111" not in sent
    assert provider.tool_results[0]["total_balance"] == 20_000


GROUNDING_CASES = [
    ("saldo_exacto", False, {"total_balance": 20_000}, "Tu saldo es $20,000.", "allowed"),
    ("diferencia", False, {"total_balance": 20_000, "expense": 15_000},
     "Te quedan $5,000.", "allowed"),
    ("porcentaje", False, {"saved_amount": 2_000, "target_amount": 10_000},
     "Llevas 20%.", "allowed"),
    ("sin_cifras", False, {"total_balance": 20_000}, "Revisa los resultados.", "allowed"),
    ("inventado", False, {"total_balance": 20_000}, "Tu saldo es $999,999.", "blocked"),
    ("sin_dato", False, {
        "transactions": [], "total_count": 0,
        "sin_dato": {"code": "transactions_empty",
                     "message": "No hay movimientos para los filtros solicitados.",
                     "period": None},
    }, "Hay 0 movimientos.", "sin_dato"),
    ("porcentaje_inventado", True, {"saved_amount": 2_000, "target_amount": 10_000},
     "Llevas 99%.", "blocked"),
    ("meses", True, {"months": 12}, "Revisa 12 meses.", "allowed"),
    ("tasa", True, {"annual_rate": 15.9}, "La tasa es 15.9%.", "allowed"),
    ("cero_real", True, {"total_balance": 0}, "Tu saldo es $0.", "allowed"),
]

HOLDOUT_CASES = [case for case in GROUNDING_CASES if case[1]]


def test_holdout_set_is_at_least_thirty_percent():
    assert len(HOLDOUT_CASES) / len(GROUNDING_CASES) >= 0.30


@pytest.mark.parametrize(
    ("_label", "_holdout", "tool_result", "text", "kind"),
    GROUNDING_CASES,
)
def test_grounding_cases_dev_and_holdout(
    monkeypatch, _label, _holdout, tool_result, text, kind,
):
    tool_name = "get_transactions" if "sin_dato" in tool_result else "get_balance"
    provider = ScriptedProvider([
        _tool_turn(tool_name),
        _text_turn(text),
        _text_turn(text),
    ])
    response = _run_live(monkeypatch, provider, tool_result, tool_name=tool_name)

    if kind == "allowed":
        assert response.message == text
        assert provider.calls == 2
    elif kind == "blocked":
        assert response.message == orch._grounding_fallback(tool_result)
        assert text not in response.message
        assert provider.calls == 3
    else:
        assert response.message == tool_result["sin_dato"]["message"]
        assert provider.calls == 2
