"""Provider health: startup degradation, /health and deterministic fallback."""
import asyncio

import pytest

from app.core import config
from app.services.agent import providers


def _mark_fresh(tmp_db):
    from app.core import database, migrate

    with database.db() as conn:
        migrate.mark_fresh_install(conn)


class FakeProvider:
    name = "openai"
    model = "fake-model"

    def __init__(self, behavior: str = "ok") -> None:
        self.behavior = behavior

    async def healthcheck(self, timeout: float = 5.0) -> dict:
        if self.behavior == "down":
            raise providers.ProviderError("proveedor caído")
        if self.behavior == "slow":
            await asyncio.sleep(timeout + 5)
        if self.behavior == "malformed":
            raise ValueError("respuesta malformada")
        if self.behavior == "no_tools":
            return {"reachable": True, "tools_supported": False}
        return {"reachable": True, "tools_supported": True}


@pytest.fixture(autouse=True)
def _clean_health():
    providers.reset_provider_health()
    yield
    providers.reset_provider_health()


def _configure(monkeypatch, provider):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_MODEL", "fake-model")
    monkeypatch.setattr(providers, "_configured_provider", lambda: provider)


def test_not_configured_reports_demo(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "AI_PROVIDER", "demo")

    status = asyncio.run(providers.check_provider_health())

    assert status["name"] == "none"
    assert status["mode"] == "demo"
    assert status["reason"] == "not_configured"
    assert providers.provider_mode() == "demo"
    assert providers.provider_health_report()["mode"] == "demo"


def test_healthy_provider_enables_live(monkeypatch):
    provider = FakeProvider("ok")
    _configure(monkeypatch, provider)

    status = asyncio.run(providers.check_provider_health(timeout=0.5))

    assert status["mode"] == "live"
    assert status["reachable"] is True
    assert status["tools_supported"] is True
    assert providers.get_provider() is provider
    assert providers.provider_mode() == "live"


def test_legacy_provider_health_gate(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "legacy-key")
    monkeypatch.setattr(config, "OPENAI_MODEL", "legacy-model")
    monkeypatch.setattr(config, "LLM_MODEL", "unified-model")

    health_provider = providers._configured_provider()
    assert isinstance(health_provider, providers.OpenAICompatibleProvider)
    assert health_provider.model == "legacy-model"
    assert providers.configured_model() == "legacy-model"

    status = asyncio.run(
        providers.check_provider_health(provider=FakeProvider("down"), timeout=0.05)
    )
    assert status["mode"] == "demo"
    assert providers.get_provider() is None
    assert providers.provider_mode() == "demo"

    asyncio.run(
        providers.check_provider_health(provider=FakeProvider("ok"), timeout=0.05)
    )
    assert isinstance(providers.get_provider(), providers.OpenAIProvider)
    assert providers.provider_mode() == "live"


def test_legacy_anthropic_uses_legacy_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "legacy-key")
    monkeypatch.setattr(config, "ANTHROPIC_MODEL", "legacy-claude")
    monkeypatch.setattr(config, "LLM_MODEL", "unified-model")

    provider = providers._configured_provider()
    assert isinstance(provider, providers.AnthropicCompatibleProvider)
    assert provider.model == "legacy-claude"
    assert providers.configured_model() == "legacy-claude"
    assert isinstance(providers.get_provider(), providers.AnthropicProvider)


@pytest.mark.parametrize(
    ("behavior", "expected_reason"),
    [
        ("down", "error:ProviderError"),
        ("slow", "timeout"),
        ("no_tools", "tools_unsupported"),
        ("malformed", "error:ValueError"),
    ],
)
def test_failed_healthcheck_degrades_without_crashing(monkeypatch, behavior, expected_reason):
    provider = FakeProvider(behavior)
    _configure(monkeypatch, provider)

    status = asyncio.run(providers.check_provider_health(timeout=0.05))

    assert status["mode"] == "demo"
    assert status["reason"] == expected_reason
    assert providers.get_provider() is None
    assert providers.provider_mode() == "demo"


@pytest.mark.parametrize(("behavior", "expected_mode"), [("ok", "live"), ("down", "demo")])
def test_backend_starts_and_health_reports_provider(tmp_db, monkeypatch, behavior, expected_mode):
    from fastapi.testclient import TestClient

    from app.main import app

    _configure(monkeypatch, FakeProvider(behavior))
    _mark_fresh(tmp_db)

    with TestClient(app) as client:
        data = client.get("/api/health").json()

    assert data["provider"]["name"] == "openai"
    assert data["provider"]["mode"] == expected_mode
    assert data["ai_mode"] == expected_mode
    assert data["prompt_version"]
    assert "mcp" in data
