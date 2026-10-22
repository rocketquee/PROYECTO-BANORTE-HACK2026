"""UI contract (A2UI-equivalent protocol).

The agent never produces executable code. It may only reference one of the
authorized component types below, with strictly validated props
(extra="forbid" rejects any unexpected field, which also blocks injection
attempts like onClick handlers). The frontend renders these specs with a
fixed registry of React components.
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class SavingsContributionCandidate(Strict):
    goal_id: int
    goal_name: str
    target_amount: float
    saved_amount: float


class SavingsContributionSpec(Strict):
    type: Literal["savings_contribution"]
    status: Literal["select_goal", "confirm_required", "completed"]
    goal_id: int | None = None
    goal_name: str | None = None
    target_amount: float | None = Field(default=None, ge=0)
    saved_amount: float | None = Field(default=None, ge=0)
    remaining_before: float | None = Field(default=None, ge=0)
    contribution_amount: float | None = Field(default=None, gt=0)
    remaining_after: float | None = Field(default=None, ge=0)
    available_balance: float | None = Field(default=None, ge=0)
    confirmation_token: str | None = Field(default=None, min_length=36, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=36, max_length=36)
    candidates: list[SavingsContributionCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contribution_state(self):
        if self.status == "select_goal" and not self.candidates:
            raise ValueError("La selección debe incluir al menos una meta.")
        if self.status in ("confirm_required", "completed") and not all((
            self.goal_id, self.goal_name, self.target_amount is not None,
            self.saved_amount is not None, self.remaining_before is not None,
            self.contribution_amount is not None, self.remaining_after is not None,
        )):
            raise ValueError("El abono debe incluir el cálculo completo.")
        if self.status == "confirm_required" and not all((
            self.confirmation_token, self.idempotency_key,
        )):
            raise ValueError("El abono requiere una confirmación verificable.")
        if self.status == "completed" and (
            self.confirmation_token or self.idempotency_key
        ):
            raise ValueError("Un abono completado no debe conservar claves de confirmación.")
        return self


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


class PurchaseOption(Strict):
    option_id: Literal["cash", "savings_12", "credit_12", "credit_18", "credit_24"]
    kind: Literal["cash", "savings", "credit"]
    label: str
    amount: float = Field(ge=0, le=10_000_000)
    months: int | None = Field(default=None, ge=1, le=120)
    monthly_payment: float = Field(ge=0)
    total_cost: float = Field(ge=0, le=20_000_000)
    monthly_balance_after: float


class PurchasePlanSpec(Strict):
    type: Literal["purchase_plan"]
    title: str
    purchase_amount: float = Field(ge=1_000, le=10_000_000)
    current_balance: float
    balance_after_cash_purchase: float
    monthly_balance: float
    fixed_payments_monthly: float = Field(ge=0)
    annual_rate: float = Field(ge=0, le=200)
    options: list[PurchaseOption] = Field(min_length=5, max_length=5)
    selected_option_id: Literal["cash", "savings_12", "credit_12", "credit_18", "credit_24"] | None = None
    goal_status: Literal["not_requested", "confirm_required", "created"] = "not_requested"
    goal_name: str | None = None
    goal_deadline: str | None = None
    goal_confirmation_token: str | None = Field(default=None, min_length=36, max_length=64)
    goal_idempotency_key: str | None = Field(default=None, min_length=36, max_length=36)
    goal_created_id: int | None = Field(default=None, gt=0)
    disclaimer: str

    @model_validator(mode="after")
    def validate_option_set(self):
        expected = {"cash", "savings_12", "credit_12", "credit_18", "credit_24"}
        actual = {option.option_id for option in self.options}
        if actual != expected:
            raise ValueError("El plan debe incluir una vez cada opción de compra.")
        if self.selected_option_id is not None and self.selected_option_id not in actual:
            raise ValueError("La opción seleccionada debe pertenecer al plan.")
        if self.goal_status == "confirm_required" and not all((
            self.goal_name, self.goal_deadline, self.goal_confirmation_token,
            self.goal_idempotency_key,
        )):
            raise ValueError("La confirmación de meta debe incluir los datos pendientes.")
        if self.goal_status == "created" and self.goal_created_id is None:
            raise ValueError("La meta creada debe incluir su identificador.")
        return self


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
        SavingsContributionSpec,
        CreditSimulatorSpec,
        PurchasePlanSpec,
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
    "trend_chart", "comparison", "timeline", "alert_list", "purchase_plan",
    "savings_contribution",
]


# ---------- agent response envelope ----------

UI_SCHEMA_VERSION = "1.0"


class PendingAction(Strict):
    id: str
    action: Literal["create_savings_goal"]
    params: dict
    description: str


class ChatMessageIn(Strict):
    role: Literal["user", "assistant"]
    content: str


class ChatResponse(Strict):
    schema_version: Literal["1.0"] = UI_SCHEMA_VERSION
    trace_id: str | None = None
    message: str
    mode: Literal["demo", "live"]
    ui: list[UISpec] = []
    tools_used: list[str] = []
    suggestions: list[str] = []
    pending_action: PendingAction | None = None
    interaction_context: dict = {}
