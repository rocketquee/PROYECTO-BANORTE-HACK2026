"""Etapa 3.1 y 3.2: estado cerrado y fecha límite validada en la capa única."""
import sqlite3
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core import database
from app.core.seed import reference_today
from app.schemas.api import GoalUpdateRequest
from app.services import domain


def _client():
    from app.main import app

    return TestClient(app)


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
