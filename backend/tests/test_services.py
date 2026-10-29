import asyncio

import pytest

from app.services import finance


def test_seed_data_and_persistence(tmp_db):
    with database_connect() as conn:
        assert finance.total_balance(conn) > 0
        accounts = finance.list_accounts(conn)
        assert len(accounts) == 3
        txs = finance.list_transactions(conn, limit=500)
        assert len(txs) > 50  # ~4 months of synthetic activity


def database_connect():
    from app.core.database import db
    return db()


def test_goal_create_update_persists(tmp_db):
    with database_connect() as conn:
        goal = finance.create_goal(conn, "Laptop nueva", 20_000, None)
        assert goal["id"] > 0
        # El ahorrado nace en cero y solo cambia por transferencias (INV-4).
        assert goal["saved_amount"] == 0
        transfer = finance.apply_transfer(conn, goal_id=goal["id"], amount=5_000,
                                          direction="account_to_goal")
        updated = transfer["goal"]
        assert updated["saved_amount"] == 5_000
        assert updated["progress_pct"] == 25.0
    # persistence across new connection
    with database_connect() as conn:
        goals = {g["name"]: g for g in finance.list_goals(conn)}
        assert goals["Laptop nueva"]["saved_amount"] == 5_000


def test_spending_analysis_only_expenses(tmp_db):
    with database_connect() as conn:
        today = __import__("datetime").date.today()
        date_from, date_to = finance.month_range(today.year, today.month)
        cats = finance.spending_by_category(conn, date_from, date_to)
        assert cats, "should have spending this month"
        assert all(c["amount"] > 0 for c in cats)
        assert pytest.approx(sum(c["pct"] for c in cats), abs=0.5) == 100.0


def test_budget_overview_shape(tmp_db):
    with database_connect() as conn:
        today = __import__("datetime").date.today()
        overview = finance.budget_overview(conn, today.year, today.month)
    assert overview["income"] > 0
    assert len(overview["categories"]) >= 8
    assert overview["available"] == pytest.approx(
        overview["income"] - overview["total_spent"], abs=0.01)


def test_invalid_month_rejected(tmp_db):
    from fastapi import HTTPException
    from app.api.routes import _parse_month
    with pytest.raises(HTTPException):
        _parse_month("2026-13")
    with pytest.raises(HTTPException):
        _parse_month("basura")
    assert _parse_month("2026-10") == (2026, 10)
