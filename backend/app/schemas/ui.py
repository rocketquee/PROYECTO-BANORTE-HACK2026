"""UI contract (A2UI-equivalent protocol).

The agent never produces executable code. It may only reference one of the
authorized component types below, with strictly validated props
(extra="forbid" rejects any unexpected field, which also blocks injection
attempts like onClick handlers). The frontend renders these specs with a
fixed registry of React components.
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- financial_summary ----------

class Metric(Strict):
    label: str
    value: str
    delta: str | None = None
    tone: Literal["positive", "negative", "neutral"] = "neutral"


class FinancialSummarySpec(Strict):
    type: Literal["financial_summary"]
    title: str
    metrics: list[Metric]
    note: str | None = None


# ---------- spending_chart ----------

class CategorySlice(Strict):
    category: str
    amount: float
    pct: float
    count: int | None = None


class SpendingChartSpec(Strict):
    type: Literal["spending_chart"]
    title: str
    period: str
    chart_type: Literal["pie", "bar"] = "pie"
    series: list[CategorySlice]


# ---------- transactions_table ----------

class TransactionItem(Strict):
    id: int
    date: str
    description: str
    category: str
    amount: float
    type: Literal["income", "expense"]


class TransactionsTableSpec(Strict):
    type: Literal["transactions_table"]
    title: str
    period_label: str
    transactions: list[TransactionItem]
    total_count: int
    categories: list[str]


# ---------- savings ----------

class SavingsGoalFormSpec(Strict):
    type: Literal["savings_goal_form"]
    title: str
    suggested_name: str | None = None
    suggested_amount: float | None = None
    suggested_deadline: str | None = None


class GoalProgress(Strict):
    id: int
    name: str
    target_amount: float
    saved_amount: float
    progress_pct: float
    deadline: str | None = None
    status: str


class SavingsProgressSpec(Strict):
    type: Literal["savings_progress"]
    title: str
    goals: list[GoalProgress]


# ---------- credit simulator ----------

class CreditParams(Strict):
    amount: float
    months: int
    annual_rate: float
    method: Literal["frances", "aleman"]


class CreditResult(Strict):
    monthly_payment: float
    total_interest: float
    total_paid: float


class ScheduleRow(Strict):
    n: int
    payment: float
    interest: float
    principal: float
    balance: float


class CreditSimulatorSpec(Strict):
    type: Literal["credit_simulator"]
    title: str
    params: CreditParams
    result: CreditResult
    schedule: list[ScheduleRow]
    disclaimer: str


# ---------- budget planner ----------

class BudgetCategory(Strict):
    category: str
    spent: float
    limit: float
    pct: float | None = None


class BudgetPlannerSpec(Strict):
    type: Literal["budget_planner"]
    title: str
    month: str
    income: float
    total_spent: float
    available: float
    categories: list[BudgetCategory]


# ---------- recommendations ----------

class RecommendationItem(Strict):
    title: str
    detail: str
    kind: Literal["fact", "suggestion"]
    basis: str  # explains where the conclusion comes from


class RecommendationListSpec(Strict):
    type: Literal["recommendation_list"]
    title: str
    items: list[RecommendationItem]


# ---------- temporal / comparison ----------

class TrendPoint(Strict):
    label: str
    amount: float
    month: str | None = None


class TrendChartSpec(Strict):
    type: Literal["trend_chart"]
    title: str
    period: str
    chart_type: Literal["line", "bar", "area"] = "line"
    series: list[TrendPoint]
    conclusion: str | None = None


class ComparisonRow(Strict):
    label: str
    value_a: str
    value_b: str


class ComparisonSpec(Strict):
    type: Literal["comparison"]
    title: str
    column_a: str
    column_b: str
    rows: list[ComparisonRow]


class TimelineItem(Strict):
    date: str
    title: str
    detail: str


class TimelineSpec(Strict):
    type: Literal["timeline"]
    title: str
    items: list[TimelineItem]


class AlertItem(Strict):
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str


class AlertListSpec(Strict):
    type: Literal["alert_list"]
    title: str
    items: list[AlertItem]


# ---------- discriminated union ----------

UISpec = Annotated[
    Union[
        FinancialSummarySpec,
        SpendingChartSpec,
        TransactionsTableSpec,
        SavingsGoalFormSpec,
        SavingsProgressSpec,
        CreditSimulatorSpec,
        BudgetPlannerSpec,
        RecommendationListSpec,
        TrendChartSpec,
        ComparisonSpec,
        TimelineSpec,
        AlertListSpec,
    ],
    Field(discriminator="type"),
]

AUTHORIZED_COMPONENTS = [
    "financial_summary", "spending_chart", "transactions_table", "savings_goal_form",
    "savings_progress", "credit_simulator", "budget_planner", "recommendation_list",
    "trend_chart", "comparison", "timeline", "alert_list",
]


# ---------- agent response envelope ----------

class PendingAction(Strict):
    id: str
    action: Literal["create_savings_goal"]
    params: dict
    description: str


class ChatMessageIn(Strict):
    role: Literal["user", "assistant"]
    content: str


class ChatResponse(Strict):
    message: str
    mode: Literal["demo", "live"]
    ui: list[UISpec] = []
    tools_used: list[str] = []
    suggestions: list[str] = []
    pending_action: PendingAction | None = None
    interaction_context: dict = {}
