"""Router determinista demo/think: reglas, umbral y degradación."""
import asyncio

import pytest

from app.core import config
from app.services.agent import providers, router


@pytest.fixture(autouse=True)
def _clean_health():
    providers.reset_provider_health()
    yield
    providers.reset_provider_health()


class _Provider:
    name = "fake"
    model = "fake-model"


@pytest.mark.parametrize("message", [
    "hola",
    "¿Cuál es mi saldo?",
    "gracias",
    "¿Cuánto gasté en supermercado este mes?",
])
def test_simple_queries_route_to_demo(message):
    decision = router.decide(message)
    assert decision.mode == "demo"
    assert decision.score < config.AGENT_ROUTER_THRESHOLD
    assert decision.degraded is False


@pytest.mark.parametrize("message", [
    "Quiero crear una meta de ahorro para un viaje",
    "Transfiere $2,000 a mi meta del auto",
    "Primero revisa mis gastos y luego crea una meta",
    "Simula un crédito de $50,000 a 24 meses y compáralo con 36 meses",
])
def test_write_or_multi_step_routes_to_think(message, monkeypatch):
    monkeypatch.setattr(router, "get_provider", lambda: _Provider())
    decision = router.decide(message)
    assert decision.mode == "think"
    assert decision.score >= config.AGENT_ROUTER_THRESHOLD
    assert decision.reason == "write_or_multi_step"


def test_threshold_is_respected(monkeypatch):
    monkeypatch.setattr(router, "get_provider", lambda: _Provider())
    message = "Quiero crear una meta de ahorro"
    assert router.decide(message).mode == "think"

    monkeypatch.setattr(config, "AGENT_ROUTER_THRESHOLD", 0.95)
    decision = router.decide(message)
    assert decision.mode == "demo"
    assert decision.score == 0.6


def test_provider_unavailable_degrades_to_demo(monkeypatch):
    monkeypatch.setattr(router, "get_provider", lambda: None)
    decision = router.decide("Quiero crear una meta de ahorro")
    assert decision.mode == "demo"
    assert decision.degraded is True
    assert decision.reason == "provider_unavailable"


def test_score_is_bounded_and_deterministic():
    message = "primero analiza mis gastos, luego crea una meta de $5,000 y también compárala"
    first = router.score_message(message)
    second = router.score_message(message)
    assert first == second
    assert 0.0 <= first <= 1.0
    assert router.score_message("") == 0.0


def test_long_ambiguous_message_adds_weight_but_stays_bounded():
    message = ("eso de ahí es lo mismo que antes y necesito que me expliques con mucho "
               "detalle cómo funciona todo el proceso completo de mi dinero")
    score = router.score_message(message)
    assert score <= 1.0
    assert score > 0.0


def test_auto_simple_forces_demo_even_with_provider(monkeypatch):
    from app.schemas.api import ChatRequest
    from app.schemas.ui import ChatResponse
    from app.services.agent import orchestrator as orch

    async def fake_demo(req, trace_id=None, session=None):
        return ChatResponse(message="motor local", mode="demo")

    monkeypatch.setattr(orch, "get_provider", lambda: _Provider())
    monkeypatch.setattr(orch, "demo_response", fake_demo)
    monkeypatch.setattr(orch.mcp_client, "session", object())

    response = asyncio.run(orch.handle_chat(
        ChatRequest(message="¿Cuál es mi saldo?"), force_demo=True,
    ))

    assert response.mode == "demo"
    assert response.message == "motor local"
