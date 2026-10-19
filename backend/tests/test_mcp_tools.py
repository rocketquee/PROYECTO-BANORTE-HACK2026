"""Tests for the MCP tool implementations (the same functions the FastMCP
server exposes over the protocol) + a real protocol-level integration check."""
import asyncio

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
                        "create_savings_goal", "update_savings_goal", "analyze_spending",
                        "calculate_credit_simulation", "get_monthly_summary", "get_budgets"}
            assert expected <= names
