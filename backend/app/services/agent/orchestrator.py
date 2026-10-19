"""Agent orchestrator.

Flow: user message → intent → MCP tools (real protocol) → validated UI specs
→ frontend components. Interactions with generated UI come back as new
messages / confirmations (the A2UI interaction loop).

Demo mode: rule-based intent detection (explicit, no API key required) but the
same real MCP tools and the same validated UI contract. The UI itself is always
composed by deterministic, audited code — never by model output.
"""
import json
import re
import unicodedata
import uuid
from datetime import date

from app.core.config import AI_PROVIDER
from app.core.database import db
from app.schemas.api import ChatRequest
from app.schemas.ui import ChatResponse, CreditParams, CreditResult, CreditSimulatorSpec, \
    PendingAction, ScheduleRow
from app.services import finance
from app.services.agent import composer
from app.services.agent.providers import ProviderError, get_provider
from app.services.mcp_client import MCPClientError, mcp_client

WRITE_TOOLS = {"create_savings_goal", "update_savings_goal"}

SYSTEM_PROMPT = """Eres el asistente financiero de "Banorte AI Finanzas", un prototipo con datos sintéticos.
Reglas:
- Obtén SIEMPRE los datos con las herramientas MCP disponibles; nunca inventes cifras.
- Puedes llamar varias herramientas antes de responder. Responde en español, con claridad.
- Diferencia hechos calculados de sugerencias. No prometas rendimientos ni apruebes créditos.
- Nunca ejecutes transferencias ni operes dinero real; no existe tal herramienta.
- Si el usuario quiere crear o modificar una meta de ahorro, llama a la herramienta sin
  confirm=true; la confirmación la pide la interfaz al usuario."""


# ---------------------------------------------------------------- helpers

def _norm(text: str) -> str:
    text = text.lower()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def detect_intent(text: str) -> str:
    t = _norm(text)
    if re.search(r"\bahorrar\b|meta de ahorro|meta financiera|fondo de\b|juntar dinero", t):
        return "savings"
    if re.search(r"credito|prestamo|simular|mensualidad|cuanto pagaria|interes", t):
        return "credit"
    if re.search(r"presupuesto|organizar|limite|distribuir|planear mis gastos", t):
        return "budget"
    if re.search(r"movimientos|transaccion|estado de cuenta|clasificar|gastos de la tarjeta", t):
        return "movements"
    if re.search(r"\bgast|analiza|en que\b|categoria", t):
        return "spending"
    return "overview"


def extract_amount(text: str) -> float | None:
    t = _norm(text)
    m = re.search(r"\$\s?([\d][\d,\.]*)", t)
    if not m:
        m = re.search(r"(\d[\d,\.]{2,})", t)
    if not m:
        return None
    raw = m.group(1).replace(",", "").rstrip(".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if "mil " in t and value < 1000:
        value *= 1000
    return value if value >= 100 else None


def _month_defaults() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


# ---------------------------------------------------------------- demo agent flows

async def _demo_overview() -> ChatResponse:
    y, m = _month_defaults()
    balance = await mcp_client.call("get_balance", {})
    summary = await mcp_client.call("get_monthly_summary", {"year": y, "month": m})
    budgets = await mcp_client.call("get_budgets", {"year": y, "month": m})
    recs = composer.build_recommendations(summary, summary.get("top_categories", []),
                                          budgets.get("categories", []))
    ui = composer.financial_summary_ui(summary, balance.get("total_balance", 0))
    return ChatResponse(
        message=(f"Tu saldo total es {composer.money(balance['total_balance'])}. En "
                 f"{summary['month_label']} ingresaste {composer.money(summary['income'])} y "
                 f"gastaste {composer.money(summary['expense'])}; tu balance del mes es "
                 f"{composer.money(summary['net'])}."),
        mode="demo",
        ui=[ui, composer.recommendation_list_ui(recs, "Recomendaciones del agente")],
        tools_used=["get_balance", "get_monthly_summary", "get_budgets"],
    )


async def _demo_spending() -> ChatResponse:
    y, m = _month_defaults()
    spending = await mcp_client.call("analyze_spending", {"year": y, "month": m})
    budgets = await mcp_client.call("get_budgets", {"year": y, "month": m})
    summary = await mcp_client.call("get_monthly_summary", {"year": y, "month": m})
    cats = spending.get("categories", [])
    recs = composer.build_recommendations(summary, cats, budgets.get("categories", []))
    top = cats[0] if cats else None
    ui = composer.spending_chart_ui(cats, summary["month_label"])
    message = (f"Este mes llevas {composer.money(sum(c['amount'] for c in cats))} de gastos. "
               + (f"Tu mayor categoría es {top['category']} con {composer.money(top['amount'])} "
                  f"({top['pct']}% del total). " if top else "")
               + "El gráfico muestra la distribución completa y abajo encontrarás "
                 "recomendaciones basadas en estos datos.")
    return ChatResponse(
        message=message, mode="demo",
        ui=[ui, composer.recommendation_list_ui(recs, "Recomendaciones sobre tus gastos")],
        tools_used=["analyze_spending", "get_budgets", "get_monthly_summary"],
    )


async def _demo_movements() -> ChatResponse:
    y, m = _month_defaults()
    date_from, _ = finance.month_range(y, m)
    txs = await mcp_client.call("get_transactions", {"date_from": date_from, "limit": 50})
    items = txs.get("transactions", [])
    expense_total = sum(t["amount"] for t in items if t["type"] == "expense")
    with db() as conn:
        cats = sorted({t["category"] for t in finance.list_transactions(conn, limit=500)})
    ui = composer.transactions_table_ui(items, txs.get("total_count", len(items)), cats,
                                        "Mes actual")
    return ChatResponse(
        message=(f"Encontré {txs.get('total_count', len(items))} movimientos este mes "
                 f"({composer.money(expense_total)} en gastos). Usa la búsqueda y los filtros "
                 "para clasificarlos."),
        mode="demo", ui=[ui], tools_used=["get_transactions"],
    )


async def _demo_savings(text: str) -> ChatResponse:
    goals = await mcp_client.call("get_savings_goals", {})
    amount = extract_amount(text)
    tools_used = ["get_savings_goals"]
    if amount:
        name = "Meta de ahorro"
        m = re.search(r"(?:para|de)\s+(el |la |mis |los )?([a-záéíóúñ][a-záéíóúñ\s]{3,39}?)(?:\s+(?:para|en|antes|este|al|de)\b|[\.!?]|$)",
                      text, re.IGNORECASE)
        if m:
            candidate = m.group(2).strip()
            if candidate and not re.search(r"\d", candidate) and "ahorrar" not in _norm(candidate):
                name = candidate.capitalize()
        deadline = composer.default_savings_deadline()
        pending = PendingAction(
            id=f"pa_{uuid.uuid4().hex[:12]}",
            action="create_savings_goal",
            params={"name": name, "target_amount": amount, "deadline": deadline},
            description=f"Crear la meta '{name}' con objetivo {composer.money(amount)}.",
        )
        register_pending(pending)
        ui = composer.savings_goal_form_ui(name=name, amount=amount, deadline=deadline)
        message = (f"Con gusto te ayudo a ahorrar {composer.money(amount)}. Revisé tus metas "
                   "actuales y preparé un formulario: ajusta nombre, importe y fecha límite, y "
                   "confirma para guardarla en la base de datos.")
        return ChatResponse(message=message, mode="demo", ui=[ui],
                            tools_used=tools_used, pending_action=pending)
    goal_list = goals.get("goals", [])
    total_saved = sum(g["saved_amount"] for g in goal_list)
    ui = composer.savings_progress_ui(goal_list)
    message = (f"Llevas {composer.money(total_saved)} ahorrados entre {len(goal_list)} metas. "
               "Puedes abonar a una meta desde aquí o pedirme crear una nueva, por ejemplo: "
               "\"ayúdame a ahorrar $5,000\".")
    return ChatResponse(message=message, mode="demo", ui=[ui], tools_used=tools_used)


async def _demo_credit(text: str) -> ChatResponse:
    amount = extract_amount(text) or 150_000
    sim = await mcp_client.call("calculate_credit_simulation",
                                {"amount": amount, "months": 24, "annual_rate": 15.9,
                                 "method": "frances"})
    ui = _credit_ui_from_result(sim)
    return ChatResponse(
        message=(f"Simulé un crédito de {composer.money(sim['amount'])} a 24 meses con una tasa "
                 f"de ejemplo de 15.9% anual: la mensualidad estimada sería "
                 f"{composer.money(sim['monthly_payment'])}. Ajusta monto, plazo y tasa en el "
                 "simulador para recalcular al instante. Es una simulación educativa, no una "
                 "oferta oficial de crédito."),
        mode="demo", ui=[ui], tools_used=["calculate_credit_simulation"],
    )


def _credit_ui_from_result(sim: dict) -> CreditSimulatorSpec:
    return CreditSimulatorSpec(type="credit_simulator",
        title="Simulador de crédito",
        params=CreditParams(amount=sim["amount"], months=sim["months"],
                            annual_rate=sim["annual_rate"], method=sim["method"]),
        result=CreditResult(monthly_payment=sim["monthly_payment"],
                            total_interest=sim["total_interest"], total_paid=sim["total_paid"]),
        schedule=[ScheduleRow(**r) for r in sim["schedule"]],
        disclaimer=sim["disclaimer"],
    )


async def _demo_budget() -> ChatResponse:
    y, m = _month_defaults()
    budgets = await mcp_client.call("get_budgets", {"year": y, "month": m})
    ui = composer.budget_planner_ui(budgets)
    exceeded = [c for c in budgets.get("categories", []) if c.get("pct") is not None and c["pct"] > 100]
    message = (f"Tu ingreso del mes es {composer.money(budgets['income'])} y llevas gastado "
               f"{composer.money(budgets['total_spent'])}; te queda disponible "
               f"{composer.money(budgets['available'])}. "
               + (f"Ojo: excediste el límite en {len(exceeded)} categoría(s): "
                  + ", ".join(c["category"] for c in exceeded) + ". " if exceeded else "")
               + "Puedes editar los límites y ver el efecto inmediato.")
    return ChatResponse(message=message, mode="demo", ui=[ui], tools_used=["get_budgets"])


async def demo_response(req: ChatRequest) -> ChatResponse:
    intent = detect_intent(req.message)
    if intent == "spending":
        return await _demo_spending()
    if intent == "movements":
        return await _demo_movements()
    if intent == "savings":
        return await _demo_savings(req.message)
    if intent == "credit":
        return await _demo_credit(req.message)
    if intent == "budget":
        return await _demo_budget()
    return await _demo_overview()


# ---------------------------------------------------------------- live agent

def _intent_from_tools(tool_results: dict) -> str:
    if "calculate_credit_simulation" in tool_results:
        return "credit"
    if "create_savings_goal" in tool_results or "update_savings_goal" in tool_results:
        return "savings"
    if "analyze_spending" in tool_results:
        return "spending"
    if "get_transactions" in tool_results:
        return "movements"
    if "get_budgets" in tool_results:
        return "budget"
    return "overview"


def _ui_from_results(tool_results: dict) -> list:
    intent = _intent_from_tools(tool_results)
    y, m = _month_defaults()
    if intent == "spending" and "categories" in tool_results.get("analyze_spending", {}):
        spending = tool_results["analyze_spending"]
        month_label = f"{finance.MONTHS_ES[m - 1].capitalize()} {y}"
        uis = [composer.spending_chart_ui(spending["categories"], month_label)]
        summary = tool_results.get("get_monthly_summary")
        if not summary:
            with db() as conn:
                summary = finance.monthly_summary(conn, y, m)
        budgets = tool_results.get("get_budgets", {})
        recs = composer.build_recommendations(summary, spending["categories"],
                                              budgets.get("categories", []))
        uis.append(composer.recommendation_list_ui(recs, "Recomendaciones sobre tus gastos"))
        return uis
    if intent == "movements" and "transactions" in tool_results.get("get_transactions", {}):
        txs = tool_results["get_transactions"]
        with db() as conn:
            cats = sorted({t["category"] for t in finance.list_transactions(conn, limit=500)})
        return [composer.transactions_table_ui(txs["transactions"], txs.get("total_count", 0),
                                               cats, "Mes actual")]
    if intent == "savings":
        with db() as conn:
            return [composer.savings_progress_ui(finance.list_goals(conn))]
    if intent == "credit" and "calculate_credit_simulation" in tool_results:
        return [_credit_ui_from_result(tool_results["calculate_credit_simulation"])]
    if intent == "budget" and "categories" in tool_results.get("get_budgets", {}):
        return [composer.budget_planner_ui(tool_results["get_budgets"])]
    with db() as conn:
        summary = finance.monthly_summary(conn, y, m)
        return [composer.financial_summary_ui(summary, finance.total_balance(conn))]


async def live_response(req: ChatRequest) -> ChatResponse:
    provider = get_provider()
    specs = mcp_client.tool_specs()
    messages = [{"role": h["role"], "content": h["content"]} for h in req.history
                if h.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": req.message})

    tool_names: list[str] = []
    tool_results: dict[str, dict] = {}
    pending: PendingAction | None = None
    final_text = ""

    for _ in range(6):
        out = await provider.chat_with_tools(SYSTEM_PROMPT, messages, specs)
        if out["tool_calls"]:
            messages.append(provider.assistant_message(out))
            for call in out["tool_calls"]:
                try:
                    args = json.loads(call.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                # Server-side guardrail: the LLM can never bypass user confirmation.
                if call["name"] in WRITE_TOOLS:
                    args["confirm"] = False
                try:
                    result = await mcp_client.call(call["name"], args)
                except MCPClientError as exc:
                    result = {"error": str(exc)}
                if (call["name"] in WRITE_TOOLS
                        and result.get("status") == "requires_confirmation"):
                    pending = PendingAction(
                        id=f"pa_{uuid.uuid4().hex[:12]}", action=call["name"],
                        params=result.get("params", {}),
                        description=result.get("message", "Confirmar cambio en metas de ahorro."),
                    )
                    register_pending(pending)
                tool_names.append(call["name"])
                tool_results[call["name"]] = result
                messages.append(provider.tool_result_message(call, result))
            continue
        final_text = out["content"] or ""
        break

    uis = _ui_from_results(tool_results)
    return ChatResponse(message=final_text or "Listo, revisa los resultados en pantalla.",
                        mode="live", ui=uis, tools_used=list(dict.fromkeys(tool_names)),
                        pending_action=pending)


# ---------------------------------------------------------------- pending actions

_PENDING: dict[str, dict] = {}


def register_pending(action: PendingAction) -> None:
    _PENDING[action.id] = {"action": action.action, "params": action.params}


async def execute_pending(action_id: str) -> dict:
    data = _PENDING.pop(action_id, None)
    if not data:
        raise MCPClientError("La acción de confirmación no existe o ya fue procesada.")
    return await mcp_client.call(data["action"], {**data["params"], "confirm": True})


# ---------------------------------------------------------------- entry point

async def handle_chat(req: ChatRequest) -> ChatResponse:
    if not mcp_client.available:
        raise MCPClientError("El servidor MCP no está disponible. Reinicia el backend.")
    if get_provider() is None or AI_PROVIDER == "demo":
        return await demo_response(req)
    try:
        return await live_response(req)
    except ProviderError as exc:
        resp = await demo_response(req)
        resp.message = (f"(Proveedor de IA no disponible: {exc}. Respondí en modo "
                        f"demostración.)\n\n{resp.message}")
        resp.mode = "demo"
        return resp
