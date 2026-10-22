"""MCP tool implementations.

Plain async functions, imported by server.py and registered with FastMCP.
They reuse the backend's service layer (parameterized SQL, shared SQLite DB)
so the MCP server and the API always see the same data.

Write operations require `confirm=True` (user authorization) and never move
real money — this is a prototype with synthetic data.
"""
import hashlib
import json
import math
import sys
import uuid
from datetime import date
from difflib import SequenceMatcher
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


# ---------------------------------------------------------------- temporal tools

def _parse_month_str(value: str) -> tuple[int, int]:
    y, m = str(value).split("-")
    y, m = int(y), int(m)
    if not (2000 <= y <= 2100 and 1 <= m <= 12):
        raise ValueError(f"Mes inválido: {value}. Use YYYY-MM.")
    return y, m


async def get_spending_trend_impl(months: int = 4, category: str | None = None) -> dict:
    with db() as conn:
        series = finance.spending_trend(conn, months, category)
    total_first, total_last = series[0]["total"], series[-1]["total"]
    return {
        "months": months,
        "category": category,
        "series": series,
        "change_pct": (round(100 * (total_last - total_first) / total_first, 1)
                       if total_first else None),
    }


async def compare_months_impl(month_a: str, month_b: str) -> dict:
    ya, ma = _parse_month_str(month_a)
    yb, mb = _parse_month_str(month_b)
    with db() as conn:
        a = finance.monthly_summary(conn, ya, ma)
        b = finance.monthly_summary(conn, yb, mb)
    return {"month_a": a, "month_b": b,
            "expense_diff": round(b["expense"] - a["expense"], 2)}


async def get_weekly_spending_impl(weeks: int = 4) -> dict:
    with db() as conn:
        return {"weeks": weeks, "series": finance.weekly_spending(conn, weeks)}


async def detect_recurring_charges_impl() -> dict:
    with db() as conn:
        items = finance.recurring_charges(conn)
    return {"charges": items,
            "monthly_total": round(sum(i["monthly_estimate"] for i in items), 2)}


async def detect_duplicates_impl() -> dict:
    with db() as conn:
        return {"duplicates": finance.detect_duplicates(conn)}


async def detect_anomalies_impl() -> dict:
    with db() as conn:
        return {"anomalies": finance.detect_anomalies(conn)}


async def project_savings_impl(monthly_amount: float, target_amount: float,
                               already_saved: float = 0) -> dict:
    if monthly_amount <= 0:
        raise ValueError("El ahorro mensual debe ser mayor a cero.")
    remaining = target_amount - already_saved
    if remaining <= 0:
        return {"months_needed": 0, "message": "Ya alcanzaste esa meta."}
    months = int(-(-remaining // monthly_amount))  # ceil
    return {"months_needed": months,
            "monthly_amount": round(monthly_amount, 2),
            "target_amount": round(target_amount, 2),
            "already_saved": round(already_saved, 2)}


async def compare_credit_terms_impl(amount: float, terms: list[int] | None = None,
                                    annual_rate: float = 15.9) -> dict:
    terms = terms or [12, 24, 36]
    results = []
    for t in terms:
        sim = credit_service.simulate_credit(amount, int(t), annual_rate)
        results.append({"months": sim["months"],
                        "monthly_payment": sim["monthly_payment"],
                        "total_interest": sim["total_interest"],
                        "total_paid": sim["total_paid"]})
    return {"amount": round(amount, 2), "annual_rate": annual_rate, "terms": results}


async def budget_vs_actual_impl(year: int | None = None, month: int | None = None) -> dict:
    with db() as conn:
        today = date.today()
        overview = finance.budget_overview(conn, year or today.year, month or today.month)
    exceeded = [c for c in overview["categories"] if c["pct"] is not None and c["pct"] > 100]
    return {**overview, "exceeded_categories": exceeded}


# ---------------------------------------------------------------- write tools
# Always require explicit user confirmation (`confirm=True`).

async def create_savings_goal_impl(name: str, target_amount: float, deadline: str | None = None,
                                   confirm: bool = False,
                                   idempotency_key: str | None = None) -> dict:
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
    if idempotency_key:
        try:
            uuid.UUID(idempotency_key)
        except (TypeError, ValueError) as exc:
            raise ValueError("La clave de idempotencia no es válida.") from exc
        target_amount = round(float(target_amount), 2)
        request_json = json.dumps(
            {"name": name, "target_amount": target_amount, "deadline": deadline},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        request_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT action, request_hash, result_json FROM idempotency_records "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["action"] != "create_savings_goal" or \
                        existing["request_hash"] != request_hash:
                    raise ValueError("La clave de idempotencia ya se usó con otros datos.")
                result = json.loads(existing["result_json"])
                result["idempotent_replay"] = True
                return result
            goal = finance.create_goal(conn, name, target_amount, deadline)
            result = {"status": "created", "goal": goal,
                      "message": f"Meta '{name}' creada."}
            conn.execute(
                "INSERT INTO idempotency_records "
                "(idempotency_key, action, request_hash, result_json) VALUES (?,?,?,?)",
                (idempotency_key, "create_savings_goal", request_hash,
                 json.dumps(result, ensure_ascii=False)),
            )
        return result
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


async def apply_savings_contribution_impl(
    goal_id: int | None,
    amount: float,
    confirm: bool = False,
    idempotency_key: str | None = None,
    goal_name: str | None = None,
) -> dict:
    if not confirm:
        return {"status": "requires_confirmation"}
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or \
            not math.isfinite(amount) or amount <= 0:
        raise ValueError("El monto del abono debe ser mayor que cero.")
    if goal_id is not None and (
        isinstance(goal_id, bool) or not isinstance(goal_id, int) or goal_id <= 0
    ):
        raise ValueError("La meta seleccionada no es válida.")
    if not idempotency_key:
        raise ValueError("El abono requiere una clave de idempotencia.")
    try:
        uuid.UUID(idempotency_key)
    except (TypeError, ValueError) as exc:
        raise ValueError("La clave de idempotencia no es válida.") from exc

    amount = round(float(amount), 2)
    request_json = json.dumps(
        {"goal_id": goal_id, "amount": amount},
        sort_keys=True, separators=(",", ":"),
    )
    request_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT action, request_hash, result_json FROM idempotency_records "
            "WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if existing["action"] != "apply_savings_contribution" or \
                    existing["request_hash"] != request_hash:
                raise ValueError("La clave de idempotencia ya se usó con otros datos.")
            result = json.loads(existing["result_json"])
            result["idempotent_replay"] = True
            return result

        if goal_id is None:
            query = " ".join((goal_name or "").casefold().split())
            all_goals = conn.execute("SELECT * FROM savings_goals").fetchall()
            ranked = sorted(
                (
                    (
                        1.0 if query == " ".join(row["name"].casefold().split())
                        else SequenceMatcher(
                            None, query, " ".join(row["name"].casefold().split())
                        ).ratio(),
                        row,
                    )
                    for row in all_goals
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            matches = [item for item in ranked if item[0] >= 0.55]
            if len(matches) > 1 and matches[0][0] - matches[1][0] < 0.08:
                return {
                    "status": "ambiguous",
                    "candidates": [
                        {"id": item[1]["id"], "name": item[1]["name"]}
                        for item in matches[:5]
                    ],
                }
            row = matches[0][1] if matches else None
            goal_id = row["id"] if row else None
        else:
            row = conn.execute(
                "SELECT * FROM savings_goals WHERE id=?",
                (goal_id,),
            ).fetchone()
        if not row:
            raise ValueError("No encontré esa meta de ahorro.")
        missing = round(max(0, row["target_amount"] - row["saved_amount"]), 2)
        if amount > missing:
            raise ValueError(
                f"El abono no puede superar lo que falta: {missing:,.2f}."
            )
        balance = finance.total_balance(conn)
        if amount > balance:
            raise ValueError(
                f"El abono supera tu saldo disponible de ${balance:,.2f}."
            )

        accounts = conn.execute(
            "SELECT id, balance FROM accounts WHERE balance > 0 ORDER BY balance DESC"
        ).fetchall()
        remaining_debit = amount
        transaction_account = None
        for account in accounts:
            debit = min(remaining_debit, account["balance"])
            if debit > 0:
                conn.execute(
                    "UPDATE accounts SET balance=balance-? WHERE id=?",
                    (debit, account["id"]),
                )
                transaction_account = transaction_account or account["id"]
                remaining_debit = round(remaining_debit - debit, 2)
            if remaining_debit <= 0:
                break
        if remaining_debit > 0:
            raise ValueError("No hay saldo suficiente en las cuentas de demostración.")

        goal = finance.update_goal(conn, goal_id, add_amount=amount)
        if not goal:
            raise ValueError("No encontré esa meta de ahorro.")
        conn.execute(
            "INSERT INTO transactions (date, description, amount, type, category, account_id) "
            "VALUES (?,?,?,?,?,?)",
            (date.today().isoformat(), f"Abono a meta: {goal['name']}",
             amount, "expense", "Ahorro", transaction_account),
        )
        result = {
            "status": "applied",
            "goal": goal,
            "amount": amount,
            "available_balance": finance.total_balance(conn),
            "message": f"Abono de ${amount:,.2f} aplicado a la meta '{goal['name']}'.",
        }
        conn.execute(
            "INSERT INTO idempotency_records "
            "(idempotency_key, action, request_hash, result_json) VALUES (?,?,?,?)",
            (idempotency_key, "apply_savings_contribution", request_hash,
             json.dumps(result, ensure_ascii=False)),
        )
    return result
