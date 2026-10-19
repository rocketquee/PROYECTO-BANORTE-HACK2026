"""Deterministic UI composer.

Turns intent + MCP tool results into validated UI specs. Both the demo agent
and the live LLM agent use it, so the JSON contract is always produced by
audited code — never by model output.
"""
from datetime import date

from app.core.database import db
from app.schemas.ui import (
    BudgetCategory, BudgetPlannerSpec, CategorySlice, CreditParams, CreditResult,
    CreditSimulatorSpec, FinancialSummarySpec, GoalProgress, Metric,
    RecommendationItem, RecommendationListSpec, SavingsGoalFormSpec,
    SavingsProgressSpec, ScheduleRow, SpendingChartSpec, TransactionItem,
    TransactionsTableSpec,
)
from app.services import credit as credit_service
from app.services import finance

CUR = "$"


def money(value: float) -> str:
    return f"{CUR}{value:,.0f}"


def financial_summary_ui(summary: dict, total_balance: float) -> FinancialSummarySpec:
    tone = "positive" if summary["net"] >= 0 else "negative"
    return FinancialSummarySpec(type="financial_summary",
        title="Resumen financiero",
        metrics=[
            Metric(label="Saldo total", value=money(total_balance), tone="neutral"),
            Metric(label="Ingresos del mes", value=money(summary["income"]), tone="positive"),
            Metric(label="Gastos del mes", value=money(summary["expense"]), tone="negative"),
            Metric(label="Balance del mes", value=money(summary["net"]), tone=tone,
                   delta=f"{summary['transaction_count']} movimientos"),
        ],
        note="Datos sintéticos de demostración.",
    )


def spending_chart_ui(categories: list[dict], month_label: str) -> SpendingChartSpec:
    return SpendingChartSpec(type="spending_chart",
        title=f"Gastos por categoría · {month_label}",
        period=month_label,
        chart_type="pie",
        series=[
            CategorySlice(category=c["category"], amount=c["amount"], pct=c["pct"], count=c["count"])
            for c in categories
        ],
    )


def transactions_table_ui(txs: list[dict], total_count: int, categories: list[str],
                          period_label: str) -> TransactionsTableSpec:
    return TransactionsTableSpec(type="transactions_table",
        title="Movimientos",
        period_label=period_label,
        transactions=[
            TransactionItem(
                id=t["id"], date=t["date"], description=t["description"],
                category=t["category"], amount=round(t["amount"], 2), type=t["type"],
            )
            for t in txs
        ],
        total_count=total_count,
        categories=categories,
    )


def savings_progress_ui(goals: list[dict]) -> SavingsProgressSpec:
    return SavingsProgressSpec(type="savings_progress",
        title="Metas de ahorro",
        goals=[
            GoalProgress(
                id=g["id"], name=g["name"], target_amount=g["target_amount"],
                saved_amount=g["saved_amount"], progress_pct=g.get("progress_pct") or 0,
                deadline=g.get("deadline"), status=g["status"],
            )
            for g in goals
        ],
    )


def savings_goal_form_ui(name: str | None = None, amount: float | None = None,
                         deadline: str | None = None) -> SavingsGoalFormSpec:
    return SavingsGoalFormSpec(type="savings_goal_form",
        title="Nueva meta de ahorro",
        suggested_name=name,
        suggested_amount=amount,
        suggested_deadline=deadline,
    )


def credit_simulator_ui(amount: float, months: int, annual_rate: float,
                        method: str = "frances") -> CreditSimulatorSpec:
    result = credit_service.simulate_credit(amount, months, annual_rate, method)
    return CreditSimulatorSpec(type="credit_simulator",
        title="Simulador de crédito",
        params=CreditParams(amount=result["amount"], months=result["months"],
                            annual_rate=result["annual_rate"], method=result["method"]),
        result=CreditResult(monthly_payment=result["monthly_payment"],
                            total_interest=result["total_interest"],
                            total_paid=result["total_paid"]),
        schedule=[ScheduleRow(**r) for r in result["schedule"]],
        disclaimer=result["disclaimer"],
    )


def budget_planner_ui(overview: dict) -> BudgetPlannerSpec:
    return BudgetPlannerSpec(type="budget_planner",
        title="Organizador de presupuesto",
        month=overview["month"],
        income=overview["income"],
        total_spent=overview["total_spent"],
        available=overview["available"],
        categories=[
            BudgetCategory(category=c["category"], spent=c["spent"], limit=c["limit"], pct=c["pct"])
            for c in overview["categories"]
        ],
    )


def build_recommendations(summary: dict, categories: list[dict],
                          budget_rows: list[dict]) -> list[RecommendationItem]:
    """Rule-based, data-grounded recommendations. Facts vs suggestions are
    clearly separated and every item states its basis (source of the number)."""
    items: list[RecommendationItem] = []
    income = summary["income"]
    expense = summary["expense"]

    if income > 0:
        rate = round(100 * (income - expense) / income, 1)
        items.append(RecommendationItem(
            title=f"Tasa de ahorro del mes: {rate}%",
            detail=(f"Ingresaste {money(income)} y gastaste {money(expense)}; tu balance es "
                    f"{money(summary['net'])}."),
            kind="fact",
            basis="Calculado con get_monthly_summary sobre tus movimientos del mes.",
        ))

    if categories:
        top = categories[0]
        items.append(RecommendationItem(
            title=f"{top['category']} concentra el {top['pct']}% de tus gastos",
            detail=f"{money(top['amount'])} en {top['count']} movimientos este mes.",
            kind="fact",
            basis="Calculado con analyze_spending sobre tus gastos del mes.",
        ))
        second = next((c for c in categories[1:] if c["pct"] >= 5), None)
        if second:
            items.append(RecommendationItem(
                title=f"Revisa {second['category']} ({second['pct']}%)",
                detail=(f"Es tu segunda categoría más alta con {money(second['amount'])}. "
                        f"Reducirla 15% liberaría ≈{money(second['amount'] * 0.15)} al mes."),
                kind="suggestion",
                basis="Estimación simple (15%) sobre datos calculados; ajústala a tu realidad.",
            ))

    for row in budget_rows:
        if row.get("pct") is not None and row["pct"] > 100:
            items.append(RecommendationItem(
                title=f"Presupuesto excedido en {row['category']}",
                detail=(f"Llevas {money(row['spent'])} de un límite de {money(row['limit'])} "
                        f"({row['pct']}%)."),
                kind="suggestion",
                basis="Comparación entre analyze_spending y los límites que definiste.",
            ))
        elif row.get("pct") is not None and row["pct"] > 85:
            items.append(RecommendationItem(
                title=f"Vas al {row['pct']}% de tu presupuesto de {row['category']}",
                detail=f"Quedan {money(max(row['limit'] - row['spent'], 0))} del límite mensual.",
                kind="fact",
                basis="Comparación entre analyze_spending y los límites que definiste.",
            ))

    return items[:6]


def recommendation_list_ui(items: list[RecommendationItem],
                           title: str = "Recomendaciones") -> RecommendationListSpec:
    return RecommendationListSpec(type="recommendation_list", title=title, items=items)


def default_savings_deadline() -> str:
    future = date.today().replace(year=date.today().year + 1)
    return future.isoformat()


def month_context(year: int | None = None, month: int | None = None) -> tuple[int, int, str, str]:
    today = date.today()
    y, m = year or today.year, month or today.month
    date_from, date_to = finance.month_range(y, m)
    return y, m, date_from, date_to
