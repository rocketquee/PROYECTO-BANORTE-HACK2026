"""Etapa 3.1–3.6: validación única, direcciones y rechazos 4xx."""
import sqlite3
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core import database
from app.core.seed import reference_today
from app.schemas.api import GoalUpdateRequest
from app.services import domain

MALICIOUS_NAME = "<script>alert(1)</script>"


def _client(**kwargs):
    from app.main import app

    return TestClient(app, **kwargs)


def _create_goal(client, name="Meta validación", target=10_000):
    response = client.post(
        "/api/goals", json={"name": name, "target_amount": target},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_goal_update_schema_accepts_only_known_status():
    with pytest.raises(ValidationError):
        GoalUpdateRequest(status="banana")
    assert GoalUpdateRequest(status="activa").status == "activa"
    assert GoalUpdateRequest(status="completada").status == "completada"


def test_patch_goal_rejects_unknown_status(tmp_db):
    with _client() as client:
        goal_id = _create_goal(client)
        response = client.patch(
            f"/api/goals/{goal_id}", json={"status": "banana"},
        )
        assert response.status_code == 422
    with database.db() as conn:
        status = conn.execute(
            "SELECT status FROM savings_goals WHERE id=?", (goal_id,),
        ).fetchone()["status"]
    assert status == "activa"


def test_seeded_savings_goals_has_status_check(tmp_db):
    with database.db() as conn:
        ddl = " ".join(conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='savings_goals'"
        ).fetchone()["sql"].split())
        assert "status IN ('activa', 'completada')" in ddl
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE savings_goals SET status='banana' WHERE id=1"
            )


def test_domain_update_goal_rejects_unknown_status(tmp_db):
    with database.db() as conn:
        with pytest.raises(domain.DomainError):
            domain.update_goal(conn, 1, status="banana")


def test_patch_goal_rejects_invalid_deadline(tmp_db):
    with _client() as client:
        goal_id = _create_goal(client)
        response = client.patch(
            f"/api/goals/{goal_id}", json={"deadline": "not-a-date"},
        )
        assert response.status_code == 422


def test_patch_goal_rejects_past_deadline(tmp_db):
    past = (reference_today() - timedelta(days=1)).isoformat()
    with _client() as client:
        goal_id = _create_goal(client)
        response = client.patch(
            f"/api/goals/{goal_id}", json={"deadline": past},
        )
        assert response.status_code == 422


def test_patch_goal_accepts_future_deadline(tmp_db):
    future = (reference_today() + timedelta(days=365)).isoformat()
    with _client() as client:
        goal_id = _create_goal(client)
        response = client.patch(
            f"/api/goals/{goal_id}", json={"deadline": future},
        )
        assert response.status_code == 200, response.text
        assert response.json()["deadline"] == future


@pytest.mark.asyncio
async def test_mcp_update_goal_rejects_invalid_deadline(tmp_db):
    from tools.finance_tools import update_savings_goal_impl

    with pytest.raises(ValueError):
        await update_savings_goal_impl(1, deadline="not-a-date", confirm=True)


@pytest.mark.asyncio
async def test_mcp_update_goal_rejects_past_deadline(tmp_db):
    from tools.finance_tools import update_savings_goal_impl

    past = (reference_today() - timedelta(days=1)).isoformat()
    with pytest.raises(ValueError):
        await update_savings_goal_impl(1, deadline=past, confirm=True)


@pytest.mark.asyncio
async def test_mcp_update_goal_accepts_future_deadline(tmp_db):
    from tools.finance_tools import update_savings_goal_impl

    future = (reference_today() + timedelta(days=365)).isoformat()
    result = await update_savings_goal_impl(1, deadline=future, confirm=True)
    assert result["goal"]["deadline"] == future


def test_patch_goal_rejects_malicious_name_without_writing(tmp_db):
    with _client() as client:
        goal_id = _create_goal(client)
        response = client.patch(
            f"/api/goals/{goal_id}", json={"name": MALICIOUS_NAME},
        )
        assert response.status_code == 422
    with database.db() as conn:
        name = conn.execute(
            "SELECT name FROM savings_goals WHERE id=?", (goal_id,),
        ).fetchone()["name"]
    assert name == "Meta validación"


@pytest.mark.asyncio
async def test_mcp_create_goal_rejects_malicious_name_without_writing(tmp_db):
    from tools.finance_tools import create_savings_goal_impl, get_savings_goals_impl

    before = (await get_savings_goals_impl())["goals"]
    with pytest.raises(ValueError, match="no permitido"):
        await create_savings_goal_impl(MALICIOUS_NAME, 5_000, confirm=True)
    after = (await get_savings_goals_impl())["goals"]
    assert len(after) == len(before)


@pytest.mark.asyncio
async def test_mcp_update_goal_rejects_malicious_name_without_writing(tmp_db):
    from tools.finance_tools import get_savings_goals_impl, update_savings_goal_impl

    goals = (await get_savings_goals_impl())["goals"]
    original = goals[0]
    with pytest.raises(ValueError, match="no permitido"):
        await update_savings_goal_impl(
            original["id"], name=MALICIOUS_NAME, confirm=True,
        )
    after = (await get_savings_goals_impl())["goals"]
    current = next(goal for goal in after if goal["id"] == original["id"])
    assert current["name"] == original["name"]


@pytest.mark.asyncio
async def test_create_goal_amount_limit_is_the_same_in_rest_and_mcp(tmp_db):
    from tools.finance_tools import create_savings_goal_impl

    limit = domain.AMOUNT_LIMITS["goal_target"][1]
    with _client() as client:
        response = client.post(
            "/api/goals",
            json={"name": "Meta límite REST", "target_amount": limit},
        )
        assert response.status_code == 201, response.text
    created = await create_savings_goal_impl(
        "Meta límite MCP", limit, confirm=True,
    )
    assert created["goal"]["target_amount"] == limit

    over_limit = limit + 0.01
    with _client() as client:
        response = client.post(
            "/api/goals",
            json={"name": "Meta excedida REST", "target_amount": over_limit},
        )
        assert response.status_code == 422
    with pytest.raises(ValueError):
        await create_savings_goal_impl(
            "Meta excedida MCP", over_limit, confirm=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("with_idempotency", [False, True])
async def test_mcp_create_goal_uses_domain_authority(tmp_db, monkeypatch,
                                                    with_idempotency):
    from tools import finance_tools

    calls = []

    def fake_domain_create(conn, name, target_amount, deadline=None):
        calls.append((name, target_amount, deadline))
        return {
            "id": 999, "name": name, "target_amount": target_amount,
            "saved_amount": 0, "progress_pct": 0, "deadline": deadline,
            "status": "activa",
        }

    def forbidden_direct_write(*_args, **_kwargs):
        raise AssertionError("MCP no debe llamar a finance.create_goal directamente")

    monkeypatch.setattr(finance_tools.domain, "create_goal", fake_domain_create)
    monkeypatch.setattr(finance_tools.finance, "create_goal", forbidden_direct_write)
    result = await finance_tools.create_savings_goal_impl(
        "Meta autoridad", 5_000, confirm=True,
        idempotency_key=str(uuid.uuid4()) if with_idempotency else None,
    )
    assert result["goal"]["id"] == 999
    assert calls == [("Meta autoridad", 5_000, None)]


@pytest.mark.asyncio
async def test_rest_and_mcp_accept_same_transfer_directions(tmp_db):
    from tools.finance_tools import (
        apply_savings_contribution_impl,
        create_savings_goal_impl,
    )

    with _client() as client:
        rest_goal_id = _create_goal(client, "Meta direcciones REST", 1_000)
        rest_deposit = client.post(
            f"/api/goals/{rest_goal_id}/transfers",
            json={
                "amount": 600,
                "direction": "account_to_goal",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert rest_deposit.status_code == 200, rest_deposit.text
        assert rest_deposit.json()["direction"] == "account_to_goal"

        rest_withdrawal = client.post(
            f"/api/goals/{rest_goal_id}/transfers",
            json={
                "amount": 600,
                "direction": "goal_to_account",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert rest_withdrawal.status_code == 200, rest_withdrawal.text
        assert rest_withdrawal.json()["direction"] == "goal_to_account"
        assert rest_withdrawal.json()["goal"]["saved_amount"] == 0

    created = await create_savings_goal_impl(
        "Meta direcciones MCP", 1_000, confirm=True,
    )
    mcp_goal_id = created["goal"]["id"]
    mcp_deposit = await apply_savings_contribution_impl(
        mcp_goal_id, 600, confirm=True, idempotency_key=str(uuid.uuid4()),
        direction="account_to_goal",
    )
    assert mcp_deposit["direction"] == "account_to_goal"

    mcp_withdrawal = await apply_savings_contribution_impl(
        mcp_goal_id, 600, confirm=True, idempotency_key=str(uuid.uuid4()),
        direction="goal_to_account",
    )
    assert mcp_withdrawal["direction"] == "goal_to_account"
    assert mcp_withdrawal["goal"]["saved_amount"] == 0


@pytest.mark.asyncio
async def test_rest_and_mcp_reject_unknown_transfer_direction(tmp_db):
    from tools.finance_tools import (
        apply_savings_contribution_impl,
        create_savings_goal_impl,
    )

    with _client() as client:
        rest_goal_id = _create_goal(client, "Meta dirección inválida REST", 1_000)
        rest_response = client.post(
            f"/api/goals/{rest_goal_id}/transfers",
            json={
                "amount": 100,
                "direction": "sideways",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert rest_response.status_code == 422
        assert "aportación o un retiro" in rest_response.json()["detail"]

    created = await create_savings_goal_impl(
        "Meta dirección inválida MCP", 1_000, confirm=True,
    )
    with pytest.raises(ValueError, match="aportación o un retiro"):
        await apply_savings_contribution_impl(
            created["goal"]["id"], 100, confirm=True,
            idempotency_key=str(uuid.uuid4()), direction="sideways",
        )


def test_patch_goal_target_below_saved_returns_409_not_500(tmp_db):
    with _client(raise_server_exceptions=False) as client:
        goal_id = _create_goal(client, "Meta bajo ahorro", 1_000)
        deposit = client.post(
            f"/api/goals/{goal_id}/transfers",
            json={
                "amount": 600,
                "direction": "account_to_goal",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert deposit.status_code == 200, deposit.text
        response = client.patch(
            f"/api/goals/{goal_id}", json={"target_amount": 500},
        )
        assert response.status_code == 409
        assert response.json()["detail"]
    with database.db() as conn:
        target = conn.execute(
            "SELECT target_amount_cents FROM savings_goals WHERE id=?",
            (goal_id,),
        ).fetchone()["target_amount_cents"]
    assert target == 100_000


def test_budget_zero_returns_422_not_500_and_does_not_write(tmp_db):
    with database.db() as conn:
        before = conn.execute(
            "SELECT monthly_limit_cents FROM budgets WHERE category='Supermercado'",
        ).fetchone()["monthly_limit_cents"]

    with _client(raise_server_exceptions=False) as client:
        response = client.post(
            "/api/budget/update",
            json={"category": "Supermercado", "monthly_limit": 0},
        )
        assert response.status_code == 422
        assert response.json()["detail"]

    with database.db() as conn:
        after = conn.execute(
            "SELECT monthly_limit_cents FROM budgets WHERE category='Supermercado'",
        ).fetchone()["monthly_limit_cents"]
    assert after == before


def test_budget_valid_update_uses_clean_domain_category(tmp_db):
    with _client() as client:
        response = client.post(
            "/api/budget/update",
            json={"category": "  Regalos  ", "monthly_limit": 2_000},
        )
        assert response.status_code == 200, response.text
        item = next(
            category for category in response.json()["categories"]
            if category["category"] == "Regalos"
        )
        assert item["limit"] == 2_000

    with database.db() as conn:
        row = conn.execute(
            "SELECT monthly_limit_cents FROM budgets WHERE category='Regalos'",
        ).fetchone()
    assert row["monthly_limit_cents"] == 200_000


def test_budget_unknown_category_is_rejected_without_write(tmp_db):
    with _client() as client:
        response = client.post(
            "/api/budget/update",
            json={"category": "Criptomonedas", "monthly_limit": 1_000},
        )
        assert response.status_code == 422
        assert "taxonomía" in response.json()["detail"]

    with database.db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM budgets WHERE category='Criptomonedas'",
        ).fetchone()[0]
    assert count == 0


def test_budget_exact_limit_is_accepted_and_out_of_range_is_rejected(tmp_db):
    limit_min, limit_max = domain.AMOUNT_LIMITS["budget_limit"]

    with _client() as client:
        exact = client.post(
            "/api/budget/update",
            json={"category": "Educación", "monthly_limit": limit_max},
        )
        assert exact.status_code == 200, exact.text
        too_small = client.post(
            "/api/budget/update",
            json={"category": "Salud", "monthly_limit": limit_min / 2},
        )
        assert too_small.status_code == 422
        too_large = client.post(
            "/api/budget/update",
            json={"category": "Hogar", "monthly_limit": limit_max + 0.01},
        )
        assert too_large.status_code == 422

    with database.db() as conn:
        saved = conn.execute(
            "SELECT monthly_limit_cents FROM budgets WHERE category='Educación'",
        ).fetchone()["monthly_limit_cents"]
    assert saved == 100_000_000
