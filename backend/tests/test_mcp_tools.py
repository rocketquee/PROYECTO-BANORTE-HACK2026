"""Tests for the MCP tool implementations (the same functions the FastMCP
server exposes over the protocol) + a real protocol-level integration check."""
import asyncio
import uuid

import pytest


@pytest.mark.asyncio
async def test_get_balance(tmp_db):
    from tools.finance_tools import get_balance_impl
    result = await get_balance_impl()
    assert result["total_balance"] > 0
    assert len(result["accounts"]) == 3


@pytest.mark.asyncio
async def test_get_transactions_filters(tmp_db):
    from tools.finance_tools import get_transactions_impl
    result = await get_transactions_impl(tx_type="expense", limit=10)
    assert result["total_count"] >= 10
    assert all(t["type"] == "expense" for t in result["transactions"])


@pytest.mark.asyncio
async def test_analyze_spending(tmp_db):
    from tools.finance_tools import analyze_spending_impl
    result = await analyze_spending_impl()
    assert result["total"] > 0
    assert result["categories"][0]["pct"] >= result["categories"][-1]["pct"]


@pytest.mark.asyncio
async def test_credit_simulation_tool(tmp_db):
    from tools.finance_tools import calculate_credit_simulation_impl
    result = await calculate_credit_simulation_impl(50_000, 12, 12.0)
    assert result["monthly_payment"] > 4_000
    with pytest.raises(ValueError):
        await calculate_credit_simulation_impl(50_000, 1, 12.0)


@pytest.mark.asyncio
async def test_create_goal_requires_confirmation(tmp_db):
    from tools.finance_tools import create_savings_goal_impl, get_savings_goals_impl
    result = await create_savings_goal_impl("Vacaciones", 8_000)
    assert result["status"] == "requires_confirmation"  # write blocked without confirm
    before = len((await get_savings_goals_impl())["goals"])
    result = await create_savings_goal_impl("Vacaciones", 8_000, confirm=True)
    assert result["status"] == "created"
    goals = (await get_savings_goals_impl())["goals"]
    assert len(goals) == before + 1
    assert any(g["name"] == "Vacaciones" and g["target_amount"] == 8_000 for g in goals)


@pytest.mark.asyncio
async def test_create_goal_idempotency_prevents_duplicate_writes(tmp_db):
    from tools.finance_tools import create_savings_goal_impl, get_savings_goals_impl

    key = str(uuid.uuid4())
    first = await create_savings_goal_impl(
        "Meta idempotente", 12_000, "2027-10-22", confirm=True,
        idempotency_key=key,
    )
    replay = await create_savings_goal_impl(
        "Meta idempotente", 12_000, "2027-10-22", confirm=True,
        idempotency_key=key,
    )
    goals = (await get_savings_goals_impl())["goals"]
    assert first["goal"]["id"] == replay["goal"]["id"]
    assert replay["idempotent_replay"] is True
    assert sum(goal["name"] == "Meta idempotente" for goal in goals) == 1
    with pytest.raises(ValueError, match="idempotencia"):
        await create_savings_goal_impl(
            "Otra meta", 12_000, "2027-10-22", confirm=True,
            idempotency_key=key,
        )


@pytest.mark.asyncio
async def test_savings_contribution_requires_confirmation_and_is_idempotent(tmp_db):
    from app.core.database import db
    from tools.finance_tools import (
        apply_savings_contribution_impl,
        create_savings_goal_impl,
        get_balance_impl,
        get_savings_goals_impl,
        get_transactions_impl,
    )

    created = await create_savings_goal_impl(
        "Meta abono idempotente", 8_000, confirm=True,
        idempotency_key=str(uuid.uuid4()),
    )
    goal_id = created["goal"]["id"]
    key = str(uuid.uuid4())
    before_balance = (await get_balance_impl())["total_balance"]
    before_transactions = (await get_transactions_impl(limit=200))["total_count"]

    unconfirmed = await apply_savings_contribution_impl(
        goal_id, 2_000, confirm=False, idempotency_key=key,
    )
    assert unconfirmed["status"] == "requires_confirmation"
    assert (await get_savings_goals_impl())["goals"][-1]["saved_amount"] == 0

    first = await apply_savings_contribution_impl(
        goal_id, 2_000, confirm=True, idempotency_key=key,
    )
    replay = await apply_savings_contribution_impl(
        goal_id, 2_000, confirm=True, idempotency_key=key,
    )
    assert first["goal"]["saved_amount"] == 2_000
    assert replay["goal"]["saved_amount"] == 2_000
    assert replay["idempotent_replay"] is True
    assert (await get_balance_impl())["total_balance"] == before_balance - 2_000
    assert (await get_transactions_impl(limit=200))["total_count"] == before_transactions + 1

    with pytest.raises(ValueError, match="lo que falta"):
        await apply_savings_contribution_impl(
            goal_id, 6_001, confirm=True, idempotency_key=str(uuid.uuid4()),
        )
    with pytest.raises(ValueError, match="idempotencia"):
        await apply_savings_contribution_impl(
            goal_id, 1_000, confirm=True, idempotency_key=key,
        )


@pytest.mark.asyncio
async def test_savings_contribution_rejects_amount_above_available_balance(tmp_db):
    from app.core.database import db
    from tools.finance_tools import apply_savings_contribution_impl, create_savings_goal_impl

    created = await create_savings_goal_impl(
        "Meta sin saldo suficiente", 10_000, confirm=True,
        idempotency_key=str(uuid.uuid4()),
    )
    with db() as conn:
        conn.execute("UPDATE accounts SET balance=0")
    with pytest.raises(ValueError, match="saldo disponible"):
        await apply_savings_contribution_impl(
            created["goal"]["id"], 100, confirm=True,
            idempotency_key=str(uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_savings_contribution_can_resolve_approximate_goal_name(tmp_db):
    from tools.finance_tools import apply_savings_contribution_impl, create_savings_goal_impl

    created = await create_savings_goal_impl(
        "Compra planeada", 10_000, confirm=True,
        idempotency_key=str(uuid.uuid4()),
    )
    result = await apply_savings_contribution_impl(
        None, 500, confirm=True, idempotency_key=str(uuid.uuid4()),
        goal_name="compra planead",
    )
    assert result["goal"]["id"] == created["goal"]["id"]


@pytest.mark.asyncio
async def test_update_goal_validation(tmp_db):
    from tools.finance_tools import update_savings_goal_impl
    with pytest.raises(ValueError):
        await update_savings_goal_impl(9999, saved_amount=100, confirm=True)


@pytest.mark.asyncio
async def test_real_mcp_protocol_discovery():
    """Integration: start the MCP server over stdio and discover tools via the protocol."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[2]
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(root / "mcp-server" / "server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            names = {t.name for t in result.tools}
            expected = {"get_balance", "get_transactions", "get_cards", "get_savings_goals",
                        "create_savings_goal", "update_savings_goal",
                        "apply_savings_contribution", "analyze_spending",
                        "calculate_credit_simulation", "get_monthly_summary", "get_budgets"}
            assert expected <= names
