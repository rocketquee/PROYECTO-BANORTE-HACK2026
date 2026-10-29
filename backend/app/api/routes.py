"""REST API routes."""
import calendar
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from app.core import config
from app.core.database import db, reconcile_database, reset_database
from app.schemas.api import (BudgetUpdateRequest, ChatRequest, ConfirmRequest,
                             CreditSimulateRequest, GoalCreateRequest, GoalTransferRequest,
                             GoalUpdateRequest)
from app.schemas.ui import ChatResponse
from app.services import credit as credit_service
from app.services import domain
from app.services import finance
from app.services import savings
from app.services.agent import orchestrator
from app.services.agent.providers import provider_mode
from app.services.mcp_client import MCPClientError, mcp_client
from datetime import date as date_cls
import os

router = APIRouter(prefix="/api")

RATE_LIMIT_MAX = 30
RATE_LIMIT_WINDOW = 10.0  # seconds
_rate_log: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(client_ip: str) -> None:
    """Simple sliding-window limiter for the chat endpoint (30 msgs / 10 s)."""
    now = time.monotonic()
    log = _rate_log[client_ip]
    while log and now - log[0] > RATE_LIMIT_WINDOW:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Estás enviando mensajes muy rápido. Espera unos segundos e inténtalo de nuevo.",
        )
    log.append(now)


def _sanitize_goal_name(name: str) -> str:
    """Removes anything that could be used as markup or injection payload."""
    cleaned = re.sub(r"[<>\{\}`]|script|on\w+=", "", name, flags=re.IGNORECASE).strip()
    return re.sub(r"\s+", " ", cleaned)


def _validate_goal(body: GoalCreateRequest) -> GoalCreateRequest:
    name = _sanitize_goal_name(body.name)
    if not (2 <= len(name) <= 80):
        raise HTTPException(status_code=422,
                            detail="El nombre debe tener entre 2 y 80 caracteres.")
    if body.target_amount <= 0 or body.target_amount > 10_000_000:
        raise HTTPException(status_code=422,
                            detail="El importe objetivo debe estar entre $1 y $10,000,000.")
    if body.deadline:
        try:
            d = date_cls.fromisoformat(body.deadline)
        except ValueError:
            raise HTTPException(status_code=422, detail="Fecha límite inválida.")
        if d < date_cls.today():
            raise HTTPException(status_code=422,
                                detail="La fecha límite no puede estar en el pasado.")
    body.name = name
    return body


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


def _last_schema_version(conn) -> str | None:
    row = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return row["version"] if row else None


@router.get("/health")
def health():
    data: dict = {
        "status": "ok",
        "services": "ok" if mcp_client.available else "degraded",
        "version": "0.1.0",
        "ai_mode": provider_mode(),
    }
    with db() as conn:
        data["schema_version"] = _last_schema_version(conn)
        try:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            table_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
        except Exception:
            fk, table_count = None, None
        data["database"] = {
            "connected": True,
            "foreign_keys": bool(fk),
            "table_count": table_count,
        }
    try:
        data["database"]["size_bytes"] = os.path.getsize(DB_PATH)
    except Exception:
        data["database"]["size_bytes"] = None
    if config.DEV_MODE:
        data["mcp_tools"] = [t.name for t in mcp_client.tools]
    return data


@router.get("/dashboard")
def dashboard(month: str | None = None):
    y, m = _parse_month(month)
    with db() as conn:
        return finance.dashboard(conn, y, m)


@router.get("/transactions")
def transactions(date_from: str | None = None, date_to: str | None = None,
                 category: str | None = None, type: str | None = None,
                 q: str | None = None, limit: int = 200):
    if type not in (None, *finance.LEDGER_TYPES):
        raise HTTPException(
            status_code=422,
            detail="type debe ser 'income', 'expense' o 'transfer'.",
        )
    with db() as conn:
        items = finance.list_transactions(conn, date_from, date_to, category, type, q, limit)
        total = finance.count_transactions(conn, date_from, date_to, category, type, q)
        categories = finance.category_taxonomy(conn)
    return {"transactions": items, "total_count": total, "categories": categories}


@router.get("/analytics/trend")
def analytics_trend(months: int = 4, category: str | None = None):
    months = max(1, min(months, 24))
    with db() as conn:
        series = finance.spending_trend(conn, months, category)
    return {"series": series}


@router.get("/goals")
def goals():
    with db() as conn:
        return {"goals": finance.list_goals(conn)}


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreateRequest):
    body = _validate_goal(body)
    with db() as conn:
        try:
            # El ahorrado nace en cero: se fija solo por transferencias (INV-4).
            goal = finance.create_goal(conn, body.name, body.target_amount, body.deadline)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return goal


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdateRequest):
    with db() as conn:
        goal = finance.update_goal(conn, goal_id, name=body.name,
                                   target_amount=body.target_amount,
                                   deadline=body.deadline, status=body.status)
    if not goal:
        raise HTTPException(status_code=404, detail="Meta no encontrada.")
    return goal


@router.post("/goals/{goal_id}/transfers")
def transfer_to_goal(goal_id: int, body: GoalTransferRequest):
    """Aporta o retira dinero de una meta como **transferencia** (INV-4).

    Es el mismo caso de uso que la herramienta MCP (`app.services.savings`):
    validación central, escritura atómica e idempotente (INV-5). El ahorrado
    no se fija con `saved_amount` ni con `add_amount`.
    """
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = savings.apply_contribution(
                conn, goal_id=goal_id, amount=body.amount,
                direction=body.direction, idempotency_key=body.idempotency_key,
            )
        except domain.DomainError as exc:
            raise HTTPException(status_code=422, detail=exc.message)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    if result.get("status") == "ambiguous":
        raise HTTPException(status_code=409, detail="Hay varias metas con ese nombre.")
    return result


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
async def agent_chat(request: Request, body: ChatRequest):
    _check_rate_limit(request.client.host if request.client else "unknown")
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
    from app.schemas.ui import SavingsProgressSpec, GoalProgress
    from app.services.agent.providers import provider_mode
    action = result.get("action")
    message = result.get("message") or "Listo, guardé el cambio."
    ui = []
    if isinstance(result.get("goal"), dict):
        with db() as conn:
            goals = finance.list_goals(conn)
        ui = [SavingsProgressSpec(
            type="savings_progress",
            title="Metas de ahorro actualizadas",
            goals=[GoalProgress(
                id=g["id"], name=g["name"], target_amount=g["target_amount"],
                saved_amount=g["saved_amount"], progress_pct=g.get("progress_pct") or 0,
                deadline=g.get("deadline"), status=g["status"],
            ) for g in goals],
        )]
    return ChatResponse(
        message=message,
        mode=provider_mode(),
        ui=ui,
        tools_used=[action] if action else [],
    )


@router.get("/ui-schema")
def ui_schema():
    """Technical contract documentation — only visible in developer mode."""
    if not config.DEV_MODE:
        raise HTTPException(status_code=404, detail="No pude hacer eso. ¿Lo intentamos de otra forma?")
    from app.schemas.ui import AUTHORIZED_COMPONENTS
    return {
        "protocol": "A2UI-equivalent JSON contract (validated with Pydantic, extra=forbid)",
        "schema_version": "1.0",
        "authorized_components": AUTHORIZED_COMPONENTS,
        "note": "The agent never produces executable code; the frontend renders only these types.",
    }


class _ResetBody:
    """Cuerpo esperado para POST /admin/reset: { "confirm": "reset" }."""

    def __init__(self, confirm: str | None = None) -> None:
        self.confirm = confirm


@router.post("/admin/reset")
async def admin_reset(request: Request):
    """Borra y vuelve a sembrar la base (solo DEV_MODE).

    Requiere body JSON { "confirm": "reset" }. Protegido: nunca disponible
    en producción.
    """
    if not config.DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="El reset de base solo está disponible en modo desarrollo.",
        )
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body.get("confirm") != "reset":
        raise HTTPException(
            status_code=400,
            detail="Se requiere { \"confirm\": \"reset\" } para confirmar el reset.",
        )
    try:
        return reset_database(confirm=True)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/admin/reconcile")
def admin_reconcile():
    """Ejecuta la reconciliación de invariantes (solo DEV_MODE)."""
    if not config.DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="La reconciliación solo está disponible en modo desarrollo.",
        )
    return reconcile_database()
