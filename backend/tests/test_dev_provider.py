"""Endpoints de desarrollo para simular la caída del proveedor (paso 5)."""
import pytest

import tools.finance_tools as ft
from app.core import config
from app.services.agent import providers
from app.services.mcp_client import mcp_client

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_monthly_summary": ft.get_monthly_summary_impl,
}


async def _real_tool(name: str, arguments: dict) -> dict:
    return await IMPLS[name](**arguments)


class FakeProvider:
    name = "openai"
    model = "fake-model"

    async def healthcheck(self, timeout: float = 5.0) -> dict:
        return {"reachable": True, "tools_supported": True}


def _mark_fresh(tmp_db):
    from app.core import database, migrate

    with database.db() as conn:
        migrate.mark_fresh_install(conn)


@pytest.fixture(autouse=True)
def _clean_provider_state():
    providers.reset_provider_health()
    providers.clear_forced_degraded()
    yield
    providers.clear_forced_degraded()
    providers.reset_provider_health()


@pytest.fixture()
def patched_lifespan(monkeypatch):
    async def _noop() -> None:
        return None

    monkeypatch.setattr(mcp_client, "start", _noop)
    monkeypatch.setattr(mcp_client, "stop", _noop)
    monkeypatch.setattr(mcp_client, "call", _real_tool)


def _client(monkeypatch, tmp_db, *, dev_mode: bool):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(config, "DEV_MODE", dev_mode)
    _mark_fresh(tmp_db)
    return TestClient(app)


def test_dev_provider_endpoints_return_404_when_dev_mode_is_off(
    tmp_db, monkeypatch, patched_lifespan,
):
    with _client(monkeypatch, tmp_db, dev_mode=False) as client:
        assert client.post("/api/dev/provider/degrade").status_code == 404
        assert client.post("/api/dev/provider/recheck").status_code == 404


def test_degrade_forces_demo_fallback_and_recheck_restores_live(
    tmp_db, monkeypatch, patched_lifespan,
):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_MODEL", "fake-model")
    monkeypatch.setattr(providers, "_configured_provider", lambda: FakeProvider())

    with _client(monkeypatch, tmp_db, dev_mode=True) as client:
        degraded = client.post("/api/dev/provider/degrade")
        assert degraded.status_code == 200
        body = degraded.json()
        assert body["forced"] is True
        assert body["provider"]["mode"] == "demo"
        assert body["provider"]["reason"] == "provider_unavailable"

        response = client.post("/api/agent/chat", json={
            "message": "¿Cuál es mi saldo?",
            "mode": "think",
            "session_id": "dev-degraded",
        })
        assert response.status_code == 200
        chat = response.json()
        assert chat["mode"] == "demo"
        assert chat["degraded"] is True
        assert chat["reason"] == "provider_unavailable"
        assert chat["ui_plan"] is not None

        recheck = client.post("/api/dev/provider/recheck")
        assert recheck.status_code == 200
        restored = recheck.json()
        assert restored["forced"] is False
        assert restored["provider"]["mode"] == "live"
        assert providers.get_provider() is not None
        assert providers.provider_mode() == "live"
