"""Request/response models for the REST API."""
from pydantic import BaseModel, ConfigDict, Field


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


class ChatRequest(Strict):
    message: str = Field(min_length=1, max_length=5000)
    history: list[dict] = []
    context: dict = {}


class ConfirmRequest(Strict):
    action_id: str
