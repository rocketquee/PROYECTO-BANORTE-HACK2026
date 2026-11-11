"""Catálogo A2UI para `ui_plan`: pantallas generadas con componentes fijos.

El modelo solo elige componentes del catálogo y copia números que ya vienen de
las herramientas MCP. Nunca produce código ni props fuera del esquema: cada
componente es un modelo Pydantic estricto (`extra="forbid"`) y el plan completo
se valida antes de llegar al frontend.

La validación numérica (`validate_ui_plan(..., tool_results=...)`) comprueba que
todo importe del plan exista en los resultados de las herramientas, de modo que
un modelo no pueda inventar cifras.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.services.agent import composer

MAX_COMPONENTS = 5
MAX_PLAN_CHARS = 20_000
MAX_MONEY = 10_000_000.0


class UIPlanError(ValueError):
    """Plan de UI inválido; el mensaje se usa como feedback del reparador."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class StrictPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatCard(StrictPlan):
    type: Literal["StatCard"]
    title: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=40)
    hint: str | None = Field(default=None, max_length=120)
    trend_pct: float | None = Field(default=None, ge=-100, le=100)
    tone: Literal["positive", "negative", "neutral"] = "neutral"


class BarItem(StrictPlan):
    label: str = Field(min_length=1, max_length=60)
    value: float = Field(ge=0, le=MAX_MONEY)


class BarChart(StrictPlan):
    type: Literal["BarChart"]
    title: str = Field(min_length=1, max_length=80)
    series: list[BarItem] = Field(min_length=1, max_length=12)
    unit: str = Field(default="MXN", max_length=12)
    note: str | None = Field(default=None, max_length=160)


class Table(StrictPlan):
    type: Literal["Table"]
    title: str = Field(min_length=1, max_length=80)
    columns: list[str] = Field(min_length=1, max_length=6)
    rows: list[list[str]] = Field(default_factory=list, max_length=50)
    note: str | None = Field(default=None, max_length=160)

    @field_validator("columns")
    @classmethod
    def _valid_columns(cls, value: list[str]) -> list[str]:
        for column in value:
            if not 1 <= len(column) <= 40:
                raise ValueError("Cada columna debe tener entre 1 y 40 caracteres.")
        return value

    @model_validator(mode="after")
    def _rows_match_columns(self):
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(
                    "Cada fila debe tener el mismo número de celdas que columnas."
                )
            for cell in row:
                if len(cell) > 120:
                    raise ValueError("Cada celda debe tener como máximo 120 caracteres.")
        return self


class ProgressRing(StrictPlan):
    type: Literal["ProgressRing"]
    title: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=0, le=100)
    target_label: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=160)


class TransferForm(StrictPlan):
    type: Literal["TransferForm"]
    title: str = Field(min_length=1, max_length=80)
    from_account: str = Field(min_length=1, max_length=60)
    to_account: str = Field(min_length=1, max_length=60)
    amount: float = Field(gt=0, le=MAX_MONEY)
    concept: str = Field(min_length=1, max_length=80)
    confirmation_text: str = Field(min_length=1, max_length=160)
    # Datos de la confirmación ya emitida por el servidor (camino demo).
    goal_id: int | None = Field(default=None, ge=1)
    confirmation_token: str | None = Field(default=None, min_length=36, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=36, max_length=36)


UIPlanComponent = Annotated[
    Union[StatCard, BarChart, Table, ProgressRing, TransferForm],
    Field(discriminator="type"),
]


class UIPlan(StrictPlan):
    title: str = Field(min_length=1, max_length=80)
    components: list[UIPlanComponent] = Field(
        default_factory=list, max_length=MAX_COMPONENTS,
    )


#: Qué herramienta MCP puede alimentar cada componente.
COMPONENT_TOOL_SOURCES: dict[str, tuple[str, ...]] = {
    "StatCard": ("get_balance", "get_monthly_summary", "calculate_credit_simulation"),
    "BarChart": ("analyze_spending", "get_spending_trend", "compare_months",
                 "get_weekly_spending"),
    "Table": ("get_transactions", "calculate_credit_simulation", "get_budgets"),
    "ProgressRing": ("get_savings_goals", "project_savings"),
    "TransferForm": ("apply_savings_contribution", "create_savings_goal"),
}

#: Números en texto: "$85,921", "85,921.00", "85921.45", "85921".
#: La coma es separador de miles y el punto decimal (formato es-MX).
_NUMBER_RE = re.compile(
    r"(?<![\d.])\$?\s*(-?(?:\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?)(?![\d])"
)

#: Props opacas que no son cifras y no deben pasar por el grounding numérico.
_UNGROUNDED_KEYS = frozenset({"confirmation_token", "idempotency_key"})


def _numbers_in_string(text: str) -> list[tuple[float, bool]]:
    """Devuelve (valor normalizado, tiene_centavos) de cada cifra del texto."""
    found: list[tuple[float, bool]] = []
    for match in _NUMBER_RE.finditer(text):
        try:
            found.append((float(match.group(1).replace(",", "")),
                          match.group(2) is not None))
        except ValueError:  # pragma: no cover - regex ya garantiza dígitos
            continue
    return found


def _collect_source_numbers(value: Any, cents: set[float],
                            pesos: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        number = float(value)
        cents.add(round(number, 2))
        pesos.add(round(number, 0))
        return
    if isinstance(value, str):
        for number, _has_cents in _numbers_in_string(value):
            cents.add(round(number, 2))
            pesos.add(round(number, 0))
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_source_numbers(item, cents, pesos)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _collect_source_numbers(item, cents, pesos)


def _collect_plan_claims(value: Any, path: str,
                         out: list[tuple[str, float, bool]]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        number = round(float(value), 2)
        out.append((path, number, number != float(round(number))))
        return
    if isinstance(value, str):
        for number, has_cents in _numbers_in_string(value):
            out.append((path, round(number, 2), has_cents))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _UNGROUNDED_KEYS:
                continue
            _collect_plan_claims(item, f"{path}.{key}" if path else key, out)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _collect_plan_claims(item, f"{path}[{index}]", out)


def _format_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(item) for item in error.get("loc", ())) or "plan"
        parts.append(f"{location}: {error.get('msg', 'valor inválido')}")
    return "; ".join(parts)[:600]


def _load_plan_input(plan: Any) -> Any:
    if isinstance(plan, str):
        text = plan.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        if len(text) > MAX_PLAN_CHARS:
            raise UIPlanError("El plan excede el tamaño máximo permitido.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise UIPlanError(f"El plan no es JSON válido: {exc.msg}.") from exc
    return plan


def _assert_grounded(plan: dict[str, Any], tool_results: dict[str, Any]) -> None:
    """Compara cifras normalizadas, no cadenas.

    - Una cifra con centavos explícitos debe coincidir con el valor exacto de
      los datos (tolerancia 0.011 por redondeo de coma flotante).
    - Una cifra sin centavos puede coincidir con el valor exacto o con su
      redondeo a pesos, porque la UI muestra importes con `composer.money`.
    - La coma es separador de miles: "85,921" son 85921 pesos, no 85.921.
    """
    source_cents: set[float] = set()
    source_pesos: set[float] = set()
    _collect_source_numbers(tool_results, source_cents, source_pesos)
    claims: list[tuple[str, float, bool]] = []
    _collect_plan_claims(plan, "", claims)
    for path, number, has_cents in claims:
        candidates = source_cents if has_cents else source_cents | source_pesos
        if any(abs(number - candidate) <= 0.011 for candidate in candidates):
            continue
        raise UIPlanError(
            f"El número {number:g} en '{path}' no aparece en los datos de las "
            "herramientas. Copia solo cifras existentes."
        )


def validate_ui_plan(plan: Any, *, tool_results: dict[str, Any] | None = None) -> UIPlan:
    """Valida un plan A2UI y, opcionalmente, que sus cifras sean reales.

    Acepta un `UIPlan`, un `dict` o el texto JSON devuelto por el modelo.
    Lanza `UIPlanError` con un mensaje apto para reinyectar como feedback.
    """
    raw = _load_plan_input(plan)
    if isinstance(raw, UIPlan):
        validated = raw
    else:
        if not isinstance(raw, dict):
            raise UIPlanError("El plan debe ser un objeto JSON.")
        if len(json.dumps(raw, ensure_ascii=False)) > MAX_PLAN_CHARS:
            raise UIPlanError("El plan excede el tamaño máximo permitido.")
        try:
            validated = UIPlan.model_validate(raw)
        except ValidationError as exc:
            raise UIPlanError(_format_error(exc)) from exc
    if tool_results is not None:
        _assert_grounded(validated.model_dump(), tool_results)
    return validated


def _money(value: float) -> str:
    return composer.money(value)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def build_ui_plan(tool_results: dict[str, Any], *,
                  pending: Any | None = None,
                  title: str = "Resumen generado") -> UIPlan:
    """Plan determinista a partir de resultados MCP reales.

    Se usa como respaldo cuando el planificador del modelo falla tras los
    reintentos. Solo copia importes y porcentajes ya calculados por el dominio.
    """
    components: list[dict[str, Any]] = []

    balance = tool_results.get("get_balance") or {}
    total_balance = _as_float(balance.get("total_balance"))
    if total_balance is not None:
        components.append({
            "type": "StatCard",
            "title": "Saldo total",
            "value": _money(total_balance),
            "hint": "Saldo en cuentas de demostración",
            "tone": "neutral",
        })

    summary = tool_results.get("get_monthly_summary") or {}
    income = _as_float(summary.get("income"))
    expense = _as_float(summary.get("expense"))
    if income is not None and expense is not None and len(components) < MAX_COMPONENTS:
        components.append({
            "type": "StatCard",
            "title": "Balance del mes",
            "value": _money(income - expense),
            "hint": f"Ingresos {_money(income)} · Gastos {_money(expense)}",
            "tone": "positive" if income >= expense else "negative",
        })

    spending = tool_results.get("analyze_spending") or {}
    categories = spending.get("categories") or []
    if categories and len(components) < MAX_COMPONENTS:
        series = [
            {"label": str(item.get("category", "Sin categoría"))[:60],
             "value": float(item.get("amount") or 0)}
            for item in categories[:8]
        ]
        if series:
            components.append({
                "type": "BarChart",
                "title": "Gasto por categoría",
                "series": series,
                "unit": "MXN",
                "note": f"Periodo {spending.get('period', 'consultado')}",
            })

    transactions = tool_results.get("get_transactions") or {}
    items = transactions.get("transactions") or []
    if items and len(components) < MAX_COMPONENTS:
        components.append({
            "type": "Table",
            "title": "Movimientos",
            "columns": ["Fecha", "Descripción", "Monto"],
            "rows": [
                [str(item.get("date", ""))[:20],
                 str(item.get("description", ""))[:60],
                 _money(float(item.get("amount") or 0))]
                for item in items[:10]
            ],
            "note": f"{transactions.get('total_count', len(items))} movimientos",
        })

    goals = tool_results.get("get_savings_goals") or {}
    goal_items = goals.get("goals") or []
    if goal_items and len(components) < MAX_COMPONENTS:
        goal = goal_items[0]
        progress = _as_float(goal.get("progress_pct"))
        if progress is not None:
            components.append({
                "type": "ProgressRing",
                "title": "Avance de meta",
                "label": str(goal.get("name", "Meta"))[:80],
                "value": max(0.0, min(100.0, progress)),
                "target_label": _money(float(goal.get("target_amount") or 0)),
                "note": f"Ahorrado {_money(float(goal.get('saved_amount') or 0))}",
            })

    if pending is not None and len(components) < MAX_COMPONENTS:
        params = getattr(pending, "params", None) or {}
        amount = _as_float(params.get("amount"))
        if amount is not None and amount > 0:
            components.append({
                "type": "TransferForm",
                "title": "Confirmar movimiento",
                "from_account": "Cuenta de origen",
                "to_account": str(params.get("goal_name") or params.get("name") or "Meta"),
                "amount": amount,
                "concept": str(getattr(pending, "description", "Movimiento solicitado"))[:80],
                "confirmation_text": "Revisa el monto y confirma con el asistente.",
                "goal_id": _as_int(params.get("goal_id")),
            })

    return UIPlan(title=title, components=components)


def plan_from_ui_specs(ui_specs: list[dict[str, Any]], *,
                       title: str = "Resumen generado") -> UIPlan:
    """Adapta los `ui` existentes (camino demo/reglas) a un `ui_plan`.

    Mantiene la paridad de cifras: el plan demo sale de los mismos números que
    ya calculó el dominio para las tarjetas deterministas.
    """
    components: list[dict[str, Any]] = []
    for spec in ui_specs:
        if len(components) >= MAX_COMPONENTS:
            break
        kind = spec.get("type")
        if kind == "financial_summary":
            for metric in (spec.get("metrics") or [])[:3]:
                if len(components) >= MAX_COMPONENTS:
                    break
                components.append({
                    "type": "StatCard",
                    "title": str(metric.get("label", "Dato"))[:80],
                    "value": str(metric.get("value", ""))[:40],
                    "hint": str(spec.get("title", ""))[:120] or None,
                    "tone": metric.get("tone", "neutral"),
                })
        elif kind == "spending_chart":
            series = [
                {"label": str(item.get("category", "Sin categoría"))[:60],
                 "value": float(item.get("amount") or 0)}
                for item in (spec.get("series") or [])[:8]
            ]
            if series:
                components.append({
                    "type": "BarChart",
                    "title": str(spec.get("title", "Gasto por categoría"))[:80],
                    "series": series,
                    "unit": "MXN",
                    "note": str(spec.get("period", ""))[:160] or None,
                })
        elif kind == "transactions_table":
            rows = [
                [str(item.get("date", ""))[:20],
                 str(item.get("description", ""))[:60],
                 _money(float(item.get("amount") or 0))]
                for item in (spec.get("transactions") or [])[:10]
            ]
            if rows:
                components.append({
                    "type": "Table",
                    "title": str(spec.get("title", "Movimientos"))[:80],
                    "columns": ["Fecha", "Descripción", "Monto"],
                    "rows": rows,
                    "note": str(spec.get("period_label", ""))[:160] or None,
                })
        elif kind == "savings_progress":
            goals = spec.get("goals") or []
            if goals:
                goal = goals[0]
                components.append({
                    "type": "ProgressRing",
                    "title": "Avance de meta",
                    "label": str(goal.get("name", "Meta"))[:80],
                    "value": max(0.0, min(100.0, float(goal.get("progress_pct") or 0))),
                    "target_label": _money(float(goal.get("target_amount") or 0)),
                    "note": f"Ahorrado {_money(float(goal.get('saved_amount') or 0))}",
                })
        elif kind == "savings_contribution":
            status = spec.get("status")
            amount = _as_float(spec.get("contribution_amount"))
            goal_name = str(spec.get("goal_name") or spec.get("requested_goal_name")
                            or "Meta")[:60]
            if status == "confirm_required" and amount and amount > 0:
                components.append({
                    "type": "TransferForm",
                    "title": "Confirmar abono a meta",
                    "from_account": "Cuenta de origen",
                    "to_account": goal_name,
                    "amount": amount,
                    "concept": f"Abono a {goal_name}"[:80],
                    "confirmation_text": (
                        f"Abonarás {_money(amount)}. Revisa y confirma."
                    )[:160],
                    "goal_id": _as_int(spec.get("goal_id")),
                    "confirmation_token": spec.get("confirmation_token"),
                    "idempotency_key": spec.get("idempotency_key"),
                })
            elif status == "completed" and amount and amount > 0:
                components.append({
                    "type": "StatCard",
                    "title": "Abono aplicado",
                    "value": _money(amount),
                    "hint": (
                        f"{goal_name}: ahorrado "
                        f"{_money(float(spec.get('saved_amount') or 0))} de "
                        f"{_money(float(spec.get('target_amount') or 0))}"
                    )[:120],
                    "tone": "positive",
                })
        elif kind == "trend_chart":
            series = [
                {"label": str(item.get("label", ""))[:60],
                 "value": float(item.get("expense", item.get("value", 0)) or 0)}
                for item in (spec.get("series") or [])[:8]
            ]
            if series:
                components.append({
                    "type": "BarChart",
                    "title": str(spec.get("title", "Tendencia"))[:80],
                    "series": series,
                    "unit": "MXN",
                    "note": str(spec.get("period_label", ""))[:160] or None,
                })
    return UIPlan(title=title, components=components)
