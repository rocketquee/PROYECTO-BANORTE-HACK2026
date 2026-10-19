"""MCP tool implementations.

Plain async functions, imported by server.py and registered with FastMCP.
They reuse the backend's service layer (parameterized SQL, shared SQLite DB)
so the MCP server and the API always see the same data.

Write operations require `confirm=True` (user authorization) and never move
real money — this is a prototype with synthetic data.
"""
import sys
from datetime import date
from pathlib import Path

# Reuse the backend service layer (documented trade-off for a prototype).
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import db  # noqa: E402
from app.services import credit as credit_service  # noqa: E402
from app.services import finance  # noqa: E402


# ---------------------------------------------------------------- read tools

async def get_balance_impl() -> dict:
    with db() as conn:
        accounts = finance.list_accounts(conn)
        return {
            "total_balance": finance.total_balance(conn),
            "accounts": accounts,
            "currency": "MXN",
            "note": "Datos sintéticos de demostración.",
        }


async def get_transactions_impl(date_from: str | None = None, date_to: str | None = None,
                                category: str | None = None, tx_type: str | None = None,
                                q: str | None = None, limit: int = 50) -> dict:
    limit = max(1, min(int(limit), 200))
    with db() as conn:
        items = finance.list_transactions(conn, date_from, date_to, category, tx_type, q, limit)
        total = finance.count_transactions(conn, date_from, date_to, category, tx_type, q)
        categories = sorted({t["category"] for t in finance.list_transactions(conn, limit=500)})
        return {"transactions": items, "total_count": total, "categories": categories,
                "filters_applied": {"date_from": date_from, "date_to": date_to,
                                    "category": category, "type": tx_type, "q": q}}


async def get_cards_impl() -> dict:
    with db() as conn:
        cards = finance.list_cards(conn)
    # Only non-sensitive demo data is exposed: no full numbers, no CVV.
    return {"cards": cards,
            "note": "Tarjetas ficticias; solo últimos 4 dígitos, nunca datos sensibles reales."}


async def get_savings_goals_impl() -> dict:
    with db() as conn:
        return {"goals": finance.list_goals(conn)}


async def analyze_spending_impl(year: int | None = None, month: int | None = None,
                                date_from: str | None = None, date_to: str | None = None) -> dict:
    with db() as conn:
        if date_from and date_to:
            categories = finance.spending_by_category(conn, date_from, date_to)
            period = f"{date_from} a {date_to}"
        else:
            today = date.today()
            y, m = year or today.year, month or today.month
            date_from_, date_to_ = finance.month_range(y, m)
            categories = finance.spending_by_category(conn, date_from_, date_to_)
            period = f"{y}-{m:02d}"
        total = round(sum(c["amount"] for c in categories), 2)
        return {"period": period, "total": total, "categories": categories}


async def calculate_credit_simulation_impl(amount: float, months: int, annual_rate: float,
                                           method: str = "frances") -> dict:
    return credit_service.simulate_credit(amount, months, annual_rate, method)


async def get_monthly_summary_impl(year: int | None = None, month: int | None = None) -> dict:
    with db() as conn:
        today = date.today()
        return finance.monthly_summary(conn, year or today.year, month or today.month)


async def get_budgets_impl(year: int | None = None, month: int | None = None) -> dict:
    with db() as conn:
        today = date.today()
        return finance.budget_overview(conn, year or today.year, month or today.month)


# ---------------------------------------------------------------- write tools
# Always require explicit user confirmation (`confirm=True`).

async def create_savings_goal_impl(name: str, target_amount: float, deadline: str | None = None,
                                   confirm: bool = False) -> dict:
    if not confirm:
        return {
            "status": "requires_confirmation",
            "params": {"name": name, "target_amount": target_amount, "deadline": deadline},
            "message": f"¿Confirmas crear la meta '{name}' con objetivo ${target_amount:,.0f}?",
        }
    if not (2 <= len(name) <= 80):
        raise ValueError("El nombre debe tener entre 2 y 80 caracteres.")
    if not (1 <= target_amount <= 100_000_000):
        raise ValueError("El importe objetivo debe estar entre $1 y $100,000,000.")
    with db() as conn:
        goal = finance.create_goal(conn, name, target_amount, deadline)
    return {"status": "created", "goal": goal,
            "message": f"Meta '{name}' creada."}


async def update_savings_goal_impl(goal_id: int, name: str | None = None,
                                   target_amount: float | None = None,
                                   saved_amount: float | None = None,
                                   deadline: str | None = None,
                                   confirm: bool = False) -> dict:
    if not confirm:
        return {
            "status": "requires_confirmation",
            "params": {"goal_id": goal_id, "name": name, "target_amount": target_amount,
                       "saved_amount": saved_amount, "deadline": deadline},
            "message": f"¿Confirmas actualizar la meta #{goal_id}?",
        }
    with db() as conn:
        goal = finance.update_goal(conn, goal_id, name=name, target_amount=target_amount,
                                   saved_amount=saved_amount, deadline=deadline)
    if not goal:
        raise ValueError(f"No existe la meta #{goal_id}.")
    return {"status": "updated", "goal": goal,
            "message": f"Meta '{goal['name']}' actualizada."}
