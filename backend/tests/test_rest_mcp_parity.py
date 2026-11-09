"""Etapa 3.8: matriz de paridad entre la API REST y las herramientas MCP.

Cada caso ejecuta la misma entrada contra una base REST y una base MCP separadas
y compara el resultado semántico o el rechazo tipado. La matriz cubre metas,
transferencias, presupuesto y errores 4xx. La prueba del arnés demuestra que una
divergencia real hace fallar la suite.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app.core import database
from app.core import migrate
from app.core import seed as seed_mod
from app.core.seed import reference_today
from app.services import domain
from app.services.mcp_catalog import ToolValidationError

Projector = Callable[[dict], Any]


class DatabasePair:
    """Dos bases sembradas de forma idéntica, una por transporte."""

    def __init__(self, tmp_path, monkeypatch):
        self.monkeypatch = monkeypatch
        self.paths = {
            "rest": tmp_path / "rest.db",
            "mcp": tmp_path / "mcp.db",
        }
        for side in ("rest", "mcp"):
            self.select(side)
            with database.db() as conn:
                seed_mod.init_db(conn)
                migrate.mark_fresh_install(conn)
        self.select("rest")

    def select(self, side: str) -> None:
        self.monkeypatch.setattr(database, "DB_PATH", self.paths[side])

    @contextmanager
    def rest(self):
        self.select("rest")
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client

    @contextmanager
    def mcp(self):
        self.select("mcp")
        yield

    def query(self, side: str, sql: str, params: tuple = ()):
        self.select(side)
        with database.db() as conn:
            return conn.execute(sql, params).fetchone()

    def execute(self, side: str, sql: str, params: tuple = ()) -> None:
        self.select(side)
        with database.db() as conn:
            conn.execute(sql, params)


@pytest.fixture()
def parity_pair(tmp_path, monkeypatch):
    return DatabasePair(tmp_path, monkeypatch)


def _error(status: int, code: str, message: str) -> dict:
    return {
        "kind": "error",
        "status": status,
        "code": code,
        "message": message,
    }


def _http_code(status: int) -> str:
    return {
        400: "bad_request",
        404: "not_found",
        409: "conflict",
        422: "validation",
    }.get(status, "http_error")


def _detail_message(response) -> str:
    payload = response.json()
    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if isinstance(detail, list):
        return "; ".join(
            str(item.get("msg", item)) if isinstance(item, dict) else str(item)
            for item in detail
        )
    return str(detail)


def _rest_outcome(response, project: Projector) -> dict:
    if response.status_code >= 400:
        return _error(
            response.status_code,
            _http_code(response.status_code),
            _detail_message(response),
        )
    return {"kind": "ok", "data": project(response.json())}


def _mcp_error(exc: Exception) -> dict | None:
    if isinstance(exc, ToolValidationError):
        return _error(422, "validation", str(exc))
    if isinstance(exc, domain.DomainError):
        return _error(422, "validation", exc.message)
    if isinstance(exc, ValueError):
        return _error(409, "conflict", str(exc))
    if isinstance(exc, LookupError):
        return _error(404, "not_found", str(exc))
    return None


def _assert_same_outcome(rest: dict, mcp: dict) -> None:
    assert rest["kind"] == mcp["kind"], (rest, mcp)
    if rest["kind"] == "ok":
        assert rest["data"] == mcp["data"], (rest, mcp)
        return
    assert rest["status"] == mcp["status"], (rest, mcp)
    assert rest["code"] == mcp["code"], (rest, mcp)
    assert rest["message"] and mcp["message"], (rest, mcp)


async def _compare(pair: DatabasePair, rest_call, mcp_call,
                   rest_project: Projector = lambda data: data,
                   mcp_project: Projector = lambda data: data) -> None:
    with pair.rest() as client:
        rest_response = rest_call(client)
    rest = _rest_outcome(rest_response, rest_project)

    with pair.mcp():
        try:
            value = await mcp_call()
        except Exception as exc:
            mcp = _mcp_error(exc)
            if mcp is None:
                raise
        else:
            mcp = {"kind": "ok", "data": mcp_project(value)}
    _assert_same_outcome(rest, mcp)


GOAL_FIELDS = ("name", "target_amount", "saved_amount", "deadline", "status")


def _goal_view(data: dict) -> dict:
    goal = data["goal"] if isinstance(data, dict) and "goal" in data else data
    return {field: goal[field] for field in GOAL_FIELDS}


def _transfer_view(data: dict) -> dict:
    return {
        "amount": data["amount"],
        "direction": data["direction"],
        "goal": _goal_view(data),
        "available_balance": data["available_balance"],
        "total_balance": data["total_balance"],
    }


def _budget_view(category: str) -> Projector:
    def project(data: dict) -> dict:
        if "budget" in data:
            item = data["budget"]
            return {
                "category": item["category"],
                "monthly_limit": item["monthly_limit"],
            }
        item = next(
            row for row in data["categories"] if row["category"] == category
        )
        return {
            "category": item["category"],
            "monthly_limit": item["limit"],
        }

    return project


async def _create_goal_pair(pair: DatabasePair, name: str, target: float,
                            deadline: str | None = None) -> tuple[int, int, str]:
    from tools.finance_tools import create_savings_goal_impl

    if deadline is None:
        deadline = (reference_today() + timedelta(days=365)).isoformat()
    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": name, "target_amount": target, "deadline": deadline},
        ),
        lambda: create_savings_goal_impl(
            name, target, deadline, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    rest_id = pair.query(
        "rest", "SELECT id FROM savings_goals WHERE name=?", (name,),
    )["id"]
    mcp_id = pair.query(
        "mcp", "SELECT id FROM savings_goals WHERE name=?", (name,),
    )["id"]
    return rest_id, mcp_id, deadline


@pytest.mark.asyncio
async def test_goal_create_parity_matrix(parity_pair):
    from tools.finance_tools import create_savings_goal_impl

    pair = parity_pair
    future = (reference_today() + timedelta(days=365)).isoformat()
    limit = domain.AMOUNT_LIMITS["goal_target"][1]

    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": "Meta paridad", "target_amount": 5_000,
                  "deadline": future},
        ),
        lambda: create_savings_goal_impl(
            "Meta paridad", 5_000, future, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": "Meta límite exacto", "target_amount": limit},
        ),
        lambda: create_savings_goal_impl(
            "Meta límite exacto", limit, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": "Meta fuera de límite", "target_amount": limit + 0.01},
        ),
        lambda: create_savings_goal_impl(
            "Meta fuera de límite", limit + 0.01, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": "<script>alert(1)</script>", "target_amount": 5_000},
        ),
        lambda: create_savings_goal_impl(
            "<script>alert(1)</script>", 5_000, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/goals",
            json={"name": "Meta paridad", "target_amount": 5_000},
        ),
        lambda: create_savings_goal_impl(
            "Meta paridad", 5_000, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )

    for side in ("rest", "mcp"):
        malicious = pair.query(
            side,
            "SELECT COUNT(*) FROM savings_goals WHERE name LIKE '%<%'",
        )[0]
        assert malicious == 0


@pytest.mark.asyncio
async def test_goal_update_parity_matrix(parity_pair):
    from tools.finance_tools import update_savings_goal_impl

    pair = parity_pair
    rest_id, mcp_id, _ = await _create_goal_pair(
        pair, "Meta editable", 5_000,
    )
    future = (reference_today() + timedelta(days=730)).isoformat()
    past = (reference_today() - timedelta(days=1)).isoformat()

    await _compare(
        pair,
        lambda client: client.patch(
            f"/api/goals/{rest_id}",
            json={"name": "Meta editada", "target_amount": 6_000,
                  "deadline": future, "status": "completada"},
        ),
        lambda: update_savings_goal_impl(
            mcp_id, name="Meta editada", target_amount=6_000,
            deadline=future, status="completada", confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.patch(
            f"/api/goals/{rest_id}", json={"status": "archivada"},
        ),
        lambda: update_savings_goal_impl(
            mcp_id, status="archivada", confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.patch(
            f"/api/goals/{rest_id}", json={"deadline": past},
        ),
        lambda: update_savings_goal_impl(
            mcp_id, deadline=past, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.patch(
            f"/api/goals/{rest_id}",
            json={"name": "<script>alert(1)</script>"},
        ),
        lambda: update_savings_goal_impl(
            mcp_id, name="<script>alert(1)</script>", confirm=True,
        ),
        _goal_view,
        _goal_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 1_000, "direction": "account_to_goal",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 1_000, "account_to_goal"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.patch(
            f"/api/goals/{rest_id}", json={"target_amount": 500},
        ),
        lambda: update_savings_goal_impl(
            mcp_id, target_amount=500, confirm=True,
        ),
        _goal_view,
        _goal_view,
    )


async def _apply_mcp_transfer(goal_id: int, amount: float, direction: str,
                              idempotency_key: str | None = None) -> dict:
    from tools.finance_tools import apply_savings_contribution_impl

    return await apply_savings_contribution_impl(
        goal_id, amount, confirm=True, direction=direction,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_transfer_parity_matrix(parity_pair):
    pair = parity_pair
    rest_id, mcp_id, _ = await _create_goal_pair(
        pair, "Meta transferencias", 1_000,
    )

    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 600, "direction": "account_to_goal",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 600, "account_to_goal"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 600, "direction": "goal_to_account",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 600, "goal_to_account"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 100, "direction": "sideways",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 100, "sideways"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 0, "direction": "account_to_goal",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 0, "account_to_goal"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 1_001, "direction": "account_to_goal",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 1_001, "account_to_goal"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 1, "direction": "goal_to_account",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 1, "goal_to_account"),
        _transfer_view,
        _transfer_view,
    )
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 100, "direction": "account_to_goal",
                  "idempotency_key": "x" * 36},
        ),
        lambda: _apply_mcp_transfer(
            mcp_id, 100, "account_to_goal", idempotency_key="x" * 36,
        ),
        _transfer_view,
        _transfer_view,
    )

    for side in ("rest", "mcp"):
        pair.execute(side, "UPDATE accounts SET balance_cents=0")
    await _compare(
        pair,
        lambda client: client.post(
            f"/api/goals/{rest_id}/transfers",
            json={"amount": 100, "direction": "account_to_goal",
                  "idempotency_key": str(uuid.uuid4())},
        ),
        lambda: _apply_mcp_transfer(mcp_id, 100, "account_to_goal"),
        _transfer_view,
        _transfer_view,
    )


@pytest.mark.asyncio
async def test_budget_parity_matrix(parity_pair):
    from tools.finance_tools import set_budget_limit_impl

    pair = parity_pair
    for side in ("rest", "mcp"):
        pair.execute(side, "DELETE FROM budgets WHERE category='Regalos'")

    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Regalos", "monthly_limit": 2_000},
        ),
        lambda: set_budget_limit_impl("Regalos", 2_000, confirm=True),
        _budget_view("Regalos"),
        _budget_view("Regalos"),
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Regalos", "monthly_limit": 3_000},
        ),
        lambda: set_budget_limit_impl("Regalos", 3_000, confirm=True),
        _budget_view("Regalos"),
        _budget_view("Regalos"),
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Regalos", "monthly_limit": 0},
        ),
        lambda: set_budget_limit_impl("Regalos", 0, confirm=True),
        _budget_view("Regalos"),
        _budget_view("Regalos"),
    )
    limit_min, limit_max = domain.AMOUNT_LIMITS["budget_limit"]
    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Regalos", "monthly_limit": limit_min / 2},
        ),
        lambda: set_budget_limit_impl(
            "Regalos", limit_min / 2, confirm=True,
        ),
        _budget_view("Regalos"),
        _budget_view("Regalos"),
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Regalos", "monthly_limit": limit_max},
        ),
        lambda: set_budget_limit_impl("Regalos", limit_max, confirm=True),
        _budget_view("Regalos"),
        _budget_view("Regalos"),
    )
    await _compare(
        pair,
        lambda client: client.post(
            "/api/budget/update",
            json={"category": "Criptomonedas", "monthly_limit": 1_000},
        ),
        lambda: set_budget_limit_impl("Criptomonedas", 1_000, confirm=True),
        _budget_view("Criptomonedas"),
        _budget_view("Criptomonedas"),
    )

    for side in ("rest", "mcp"):
        unknown = pair.query(
            side,
            "SELECT COUNT(*) FROM budgets WHERE category='Criptomonedas'",
        )[0]
        assert unknown == 0

    before = pair.query(
        "mcp",
        "SELECT monthly_limit_cents FROM budgets WHERE category='Supermercado'",
    )["monthly_limit_cents"]
    with pair.mcp():
        pending = await set_budget_limit_impl(
            "Supermercado", 1_234, confirm=False,
        )
    assert pending["status"] == "requires_confirmation"
    after = pair.query(
        "mcp",
        "SELECT monthly_limit_cents FROM budgets WHERE category='Supermercado'",
    )["monthly_limit_cents"]
    assert after == before


def test_parity_harness_detects_divergence():
    ok = {"kind": "ok", "data": {"category": "Regalos", "monthly_limit": 2_000}}
    with pytest.raises(AssertionError):
        _assert_same_outcome(
            ok,
            {"kind": "ok", "data": {"category": "Regalos", "monthly_limit": 3_000}},
        )
    with pytest.raises(AssertionError):
        _assert_same_outcome(
            ok, _error(422, "validation", "categoría inválida"),
        )
    with pytest.raises(AssertionError):
        _assert_same_outcome(
            _error(422, "validation", "categoría inválida"),
            _error(409, "conflict", "categoría inválida"),
        )
