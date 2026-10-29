"""Deterministic UI composer.

Turns intent + tool results into validated UI specs. Both the demo agent
and the live LLM agent use it, so the JSON contract is always produced by
audited code — never by model output.

All user-visible text uses business language only: no tool names, protocols
or internal architecture details (those belong to developer mode).
"""
from datetime import date

from app.core import money as money_mod
from app.schemas.ui import (
    AlertItem, AlertListSpec, BudgetCategory, BudgetPlannerSpec, CategorySlice,
    ComparisonRow, ComparisonSpec, CreditParams, CreditResult, CreditSimulatorSpec,
    FinancialSummarySpec, GoalProgress, Metric, RecommendationItem,
    PurchaseOption, PurchasePlanSpec, RecommendationListSpec, SavingsGoalFormSpec,
    SavingsProgressSpec, ScheduleRow,
    SpendingChartSpec, TimelineItem, TimelineSpec, TransactionItem,
    TransactionsTableSpec, TrendChartSpec, TrendPoint,
)
from app.services import credit as credit_service

CUR = "$"

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def money(value: float) -> str:
    """Mexican format: $14,800 · negatives as -$8,673 (never $-8,673)."""
    if value < 0:
        return f"-{CUR}{abs(value):,.0f}"
    return f"{CUR}{value:,.0f}"


def money2(value: float) -> str:
    if value < 0:
        return f"-{CUR}{abs(value):,.2f}"
    return f"{CUR}{value:,.2f}"


def long_date(iso: str) -> str:
    """Formats an ISO date in Mexican style: '18 de octubre de 2026'."""
    try:
        y, m, d = (int(p) for p in iso.split("-"))
        return f"{d} de {MONTHS_ES[m - 1]} de {y}"
    except (ValueError, IndexError):
        return iso


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


def spending_chart_ui(categories: list[dict], month_label: str,
                      chart_type: str = "pie") -> SpendingChartSpec:
    return SpendingChartSpec(type="spending_chart",
        title=f"Gastos por categoría · {month_label}",
        period=month_label,
        chart_type=chart_type if chart_type in ("pie", "bar") else "pie",
        series=[
            CategorySlice(category=c["category"], amount=c["amount"], pct=c["pct"], count=c["count"])
            for c in categories
        ],
    )


def trend_chart_ui(series: list[dict], title: str, period: str,
                   chart_type: str = "line", conclusion: str | None = None) -> TrendChartSpec:
    return TrendChartSpec(type="trend_chart",
        title=title,
        period=period,
        chart_type=chart_type if chart_type in ("line", "bar", "area") else "line",
        series=[TrendPoint(label=p["label"], amount=p["total"], month=p.get("month"))
                for p in series],
        conclusion=conclusion,
    )


def comparison_ui(title: str, column_a: str, column_b: str,
                  rows: list[tuple[str, str, str]]) -> ComparisonSpec:
    return ComparisonSpec(type="comparison",
        title=title, column_a=column_a, column_b=column_b,
        rows=[ComparisonRow(label=l, value_a=a, value_b=b) for l, a, b in rows],
    )


def timeline_ui(title: str, items: list[dict]) -> TimelineSpec:
    return TimelineSpec(type="timeline", title=title,
        items=[TimelineItem(date=i["date"], title=i["title"], detail=i["detail"])
               for i in items])


def alert_list_ui(title: str, items: list[dict]) -> AlertListSpec:
    return AlertListSpec(type="alert_list", title=title,
        items=[AlertItem(severity=i.get("severity", "info"), title=i["title"],
                         detail=i["detail"]) for i in items])


def transactions_table_ui(txs: list[dict], total_count: int, categories: list[str],
                          period_label: str) -> TransactionsTableSpec:
    return TransactionsTableSpec(type="transactions_table",
        title="Movimientos",
        period_label=period_label,
        transactions=[
            TransactionItem(
                id=t["id"], date=t["date"], description=t["description"],
                category=t["category"], amount=t["amount"], type=t["type"],
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


def purchase_plan_ui(
    amount: float,
    current_balance: float,
    monthly_balance: float,
    fixed_payments_monthly: float,
    annual_rate: float,
    options: list[PurchaseOption],
    selected_option_id: str | None = None,
) -> PurchasePlanSpec:
    return PurchasePlanSpec(
        type="purchase_plan",
        title="Plan de compra",
        purchase_amount=amount,
        current_balance=current_balance,
        balance_after_cash_purchase=current_balance - amount,
        monthly_balance=monthly_balance,
        fixed_payments_monthly=fixed_payments_monthly,
        annual_rate=annual_rate,
        options=options,
        selected_option_id=selected_option_id,
        disclaimer=(
            f"Simulación educativa. Las opciones de crédito usan una tasa ilustrativa de "
            f"{annual_rate}% anual, no son una oferta ni una aprobación. El ahorro se calcula "
            "sin rendimientos y en 12 meses."
        ),
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
    clearly separated and every item states its basis in business language."""
    items: list[RecommendationItem] = []
    income = summary["income"]
    expense = summary["expense"]

    if income > 0:
        # Tasa de ahorro (INV-7): porcentaje sobre centavos exactos; el neto
        # puede ser negativo, así que la conversión es con signo.
        rate = money_mod.pct(money_mod.to_cents_signed(summary["net"]),
                             money_mod.to_cents(income))
        items.append(RecommendationItem(
            title=f"Tasa de ahorro del mes: {rate}%",
            detail=(f"Ingresaste {money(income)} y gastaste {money(expense)}; tu balance es "
                    f"{money(summary['net'])}."),
            kind="fact",
            basis="Calculado con tus ingresos y gastos del mes.",
        ))

    if categories:
        top = categories[0]
        items.append(RecommendationItem(
            title=f"{top['category']} concentra el {top['pct']}% de tus gastos",
            detail=f"{money(top['amount'])} en {top['count']} movimientos este mes.",
            kind="fact",
            basis="Calculado con tus movimientos del mes.",
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
                basis="Comparación entre tus gastos y los límites que definiste.",
            ))
        elif row.get("pct") is not None and row["pct"] > 85:
            items.append(RecommendationItem(
                title=f"Vas al {row['pct']}% de tu presupuesto de {row['category']}",
                detail=f"Quedan {money(max(row['limit'] - row['spent'], 0))} del límite mensual.",
                kind="fact",
                basis="Comparación entre tus gastos y los límites que definiste.",
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
    from app.services import finance
    date_from, date_to = finance.month_range(y, m)
    return y, m, date_from, date_to
