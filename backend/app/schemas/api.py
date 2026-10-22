"""Request/response models for the REST API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreditSimulateRequest(Strict):
    amount: float = Field(gt=0, le=10_000_000)
    months: int = Field(ge=3, le=120)
    annual_rate: float = Field(ge=0, le=200)
    method: str = "frances"


class GoalCreateRequest(Strict):
    name: str = Field(min_length=2, max_length=80)
    target_amount: float = Field(gt=0, le=10_000_000)
    deadline: str | None = None
    saved_amount: float = Field(default=0, ge=0, le=10_000_000)


class GoalUpdateRequest(Strict):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    target_amount: float | None = Field(default=None, gt=0, le=10_000_000)
    add_amount: float | None = Field(default=None, gt=0, le=10_000_000)
    deadline: str | None = None
    status: str | None = None


class BudgetUpdateRequest(Strict):
    category: str = Field(min_length=2, max_length=60)
    monthly_limit: float = Field(ge=0, le=1_000_000)


class PurchaseOptionSelectedPayload(Strict):
    option_id: Literal["cash", "savings_12", "credit_12", "credit_18", "credit_24"]
    confirmation_token: str | None = Field(default=None, min_length=36, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=36, max_length=36)


class SavingsGoalSelectedPayload(Strict):
    goal_id: int = Field(gt=0)


class SavingsContributionAmountPayload(Strict):
    amount: float = Field(gt=0, le=10_000_000)


class SavingsContributionConfirmedPayload(Strict):
    goal_id: int = Field(gt=0)
    amount: float = Field(gt=0, le=10_000_000)
    confirmation_token: str = Field(min_length=36, max_length=64)
    idempotency_key: str = Field(min_length=36, max_length=36)


class UIEventIn(Strict):
    id: str = Field(min_length=8, max_length=128)
    type: Literal[
        "purchase_option_selected",
        "purchase_goal_create_requested",
        "purchase_goal_confirmed",
        "savings_goal_selected",
        "savings_contribution_amount_changed",
        "savings_contribution_confirmed",
    ]
    payload: PurchaseOptionSelectedPayload | SavingsGoalSelectedPayload | \
        SavingsContributionAmountPayload | SavingsContributionConfirmedPayload
    trace_id: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_event_payload(self):
        if self.type == "purchase_goal_create_requested" and \
                (not isinstance(self.payload, PurchaseOptionSelectedPayload)
                 or self.payload.option_id != "savings_12"):
            raise ValueError("Solo puede solicitarse una meta desde la opción de ahorro.")
        if self.type == "purchase_goal_confirmed":
            if not isinstance(self.payload, PurchaseOptionSelectedPayload) or \
                    self.payload.option_id != "savings_12" or not all((
                self.payload.confirmation_token, self.payload.idempotency_key,
            )):
                raise ValueError("La confirmación requiere la opción y sus claves.")
        elif isinstance(self.payload, PurchaseOptionSelectedPayload) and \
                (self.payload.confirmation_token or self.payload.idempotency_key):
            raise ValueError("Este evento no puede incluir claves de confirmación.")
        if self.type == "savings_goal_selected" and not isinstance(
            self.payload, SavingsGoalSelectedPayload
        ):
            raise ValueError("La selección de meta requiere su identificador.")
        if self.type == "savings_contribution_amount_changed" and not isinstance(
            self.payload, SavingsContributionAmountPayload
        ):
            raise ValueError("El cambio de monto requiere un importe válido.")
        if self.type == "savings_contribution_confirmed" and not isinstance(
            self.payload, SavingsContributionConfirmedPayload
        ):
            raise ValueError("La confirmación requiere los datos del abono.")
        return self


class ChatRequest(Strict):
    message: str = Field(min_length=1, max_length=5000)
    history: list[dict] = []
    context: dict = {}
    ui_event: UIEventIn | None = None


class ConfirmRequest(Strict):
    action_id: str
