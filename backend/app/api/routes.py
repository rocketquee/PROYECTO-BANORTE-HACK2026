"""REST API routes."""
import calendar

from fastapi import APIRouter, HTTPException

from app.core.database import db
from app.schemas.api import (BudgetUpdateRequest, ChatRequest, ConfirmRequest,
                             CreditSimulateRequest, GoalCreateRequest, GoalUpdateRequest)
from app.schemas.ui import AUTHORIZED_COMPONENTS, ChatResponse
from app.services import credit as credit_service
from app.services import finance
from app.services.agent import orchestrator
from app.services.mcp_client import MCPClientError, mcp_client
from datetime import date as date_cls

router = APIRouter(prefix="/api")


def _parse_month(month: str | None) -> tuple[int, int]:
    today = date_cls.today()
    if not month:
        return today.year, today.month
    try:
        y, m = month.split("-")
        y, m = int(y), int(m)
        if not (2000 <= y <= 2100 and 1 <= m <= 12):
            raise ValueError
        return y, m
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="Formato de mes inválido. Use YYYY-MM.")


@router.get("/health")
def health():
    return {
        "status": "ok",
        "mcp_available": mcp_client.available,
        "mcp_tools": [t.name for t in mcp_client.tools],
    }


@router.get("/dashboard")
def dashboard(month: str | None = None):
    y, m = _parse_month(month)
    with db() as conn:
        return finance.dashboard(conn, y, m)


@router.get("/transactions")
def transactions(date_from: str | None = None, date_to: str | None = None,
                 category: str | None = None, type: str | None = None,
                 q: str | None = None, limit: int = 200):
    if type not in (None, "income", "expense"):
        raise HTTPException(status_code=422, detail="type debe ser 'income' o 'expense'.")
    with db() as conn:
        items = finance.list_transactions(conn, date_from, date_to, category, type, q, limit)
        total = finance.count_transactions(conn, date_from, date_to, category, type, q)
        categories = sorted({t["category"] for t in finance.list_transactions(conn, limit=500)})
    return {"transactions": items, "total_count": total, "categories": categories}


@router.get("/goals")
def goals():
    with db() as conn:
        return {"goals": finance.list_goals(conn)}


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreateRequest):
    with db() as conn:
        goal = finance.create_goal(conn, body.name, body.target_amount, body.deadline,
                                   body.saved_amount)
    return goal


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdateRequest):
    with db() as conn:
        goal = finance.update_goal(conn, goal_id, name=body.name,
                                   target_amount=body.target_amount,
                                   add_amount=body.add_amount, deadline=body.deadline,
                                   status=body.status)
    if not goal:
        raise HTTPException(status_code=404, detail="Meta no encontrada.")
    return goal


@router.post("/credit/simulate")
def credit_simulate(body: CreditSimulateRequest):
    try:
        return credit_service.simulate_credit(body.amount, body.months, body.annual_rate,
                                              body.method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/budget")
def budget(month: str | None = None):
    y, m = _parse_month(month)
    with db() as conn:
        return finance.budget_overview(conn, y, m)


@router.post("/budget/update")
def budget_update(body: BudgetUpdateRequest):
    with db() as conn:
        finance.set_budget_limit(conn, body.category, body.monthly_limit)
        today = date_cls.today()
        return finance.budget_overview(conn, today.year, today.month)


@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(body: ChatRequest):
    try:
        return await orchestrator.handle_chat(body)
    except MCPClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/agent/confirm", response_model=ChatResponse)
async def agent_confirm(body: ConfirmRequest):
    try:
        result = await orchestrator.execute_pending(body.action_id)
    except MCPClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    goal = result.get("goal") or result
    with db() as conn:
        ui = finance.list_goals(conn)
    from app.schemas.ui import SavingsProgressSpec, GoalProgress
    from app.services.agent.providers import provider_mode
    amount = goal.get("target_amount", 0)
    message = (f"Listo: {result.get('message', 'cambio guardado')} "
               f"La meta '{goal.get('name')}' quedó registrada con objetivo "
               f"${amount:,.0f}.")
    return ChatResponse(
        message=message,
        mode=provider_mode(),
        ui=[SavingsProgressSpec(
            type="savings_progress",
            title="Metas de ahorro actualizadas",
            goals=[GoalProgress(
                id=g["id"], name=g["name"], target_amount=g["target_amount"],
                saved_amount=g["saved_amount"], progress_pct=g.get("progress_pct") or 0,
                deadline=g.get("deadline"), status=g["status"],
            ) for g in ui],
        )],
        tools_used=["create_savings_goal"],
    )


@router.get("/ui-schema")
def ui_schema():
    return {
        "protocol": "A2UI-equivalent JSON contract (validated with Pydantic, extra=forbid)",
        "authorized_components": AUTHORIZED_COMPONENTS,
        "note": "The agent never produces executable code; the frontend renders only these types.",
    }
