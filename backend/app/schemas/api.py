"""Request/response models for the REST API."""
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services import domain


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreditSimulateRequest(Strict):
    amount: float = Field(gt=0, le=10_000_000)
    months: int = Field(ge=3, le=120)
    annual_rate: float = Field(ge=0, le=200)
    method: str = "frances"


GOAL_TARGET_MIN, GOAL_TARGET_MAX = domain.AMOUNT_LIMITS["goal_target"]
BUDGET_LIMIT_MIN, BUDGET_LIMIT_MAX = domain.AMOUNT_LIMITS["budget_limit"]


class GoalCreateRequest(Strict):
    """Datos declarativos de una meta. El ahorrado **no** se fija aquí: nace en
    cero y solo cambia por transferencias confirmadas (INV-4)."""

    name: str = Field(min_length=domain.GOAL_NAME_MIN,
                      max_length=domain.GOAL_NAME_MAX)
    target_amount: float = Field(ge=GOAL_TARGET_MIN, le=GOAL_TARGET_MAX)
    deadline: str | None = None


GoalStatus = Literal["activa", "completada"]


class GoalUpdateRequest(Strict):
    """Edita los datos declarativos de una meta. El ahorrado no se edita aquí:
    solo cambia por transferencias confirmadas (INV-4)."""

    name: str | None = Field(default=None, min_length=domain.GOAL_NAME_MIN,
                             max_length=domain.GOAL_NAME_MAX)
    target_amount: float | None = Field(default=None, ge=GOAL_TARGET_MIN,
                                        le=GOAL_TARGET_MAX)
    deadline: str | None = None
    status: GoalStatus | None = None


class GoalTransferRequest(Strict):
    """Transferencia cuenta↔meta confirmada. `direction` se valida en la capa
    de dominio (una sola definición de los sentidos válidos)."""

    amount: float = Field(gt=0, le=10_000_000)
    direction: str = "account_to_goal"
    idempotency_key: str = Field(min_length=36, max_length=36)

    @field_validator("idempotency_key")
    @classmethod
    def _validate_idempotency_key(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "La clave de idempotencia no es un UUID válido."
            ) from exc
        return value


class BudgetUpdateRequest(Strict):
    category: str = Field(min_length=domain.BUDGET_CATEGORY_MIN,
                          max_length=domain.BUDGET_CATEGORY_MAX)
    monthly_limit: float = Field(ge=BUDGET_LIMIT_MIN, le=BUDGET_LIMIT_MAX)


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
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex,
                            min_length=1, max_length=128)
    history: list[dict] = []
    context: dict = {}
    ui_event: UIEventIn | None = None


class ConfirmRequest(Strict):
    action_id: str = Field(min_length=8, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)


class LoginRequest(Strict):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
