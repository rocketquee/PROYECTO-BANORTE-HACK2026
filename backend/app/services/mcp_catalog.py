"""Catálogo único de herramientas MCP.

Este módulo es la fuente de verdad de nombre, descripción, contrato de entrada,
riesgo, permisos, confirmación, idempotencia y contrato de salida de cada
herramienta. El servidor MCP, el agente y las pruebas importan de aquí; no se
mantienen listas paralelas.

La validación de entrada es estricta: `extra="forbid"` rechaza campos
desconocidos y cada modelo declara límites, enums y formatos. La ejecución MCP
la aplica antes de invocar la herramienta; las implementaciones también pueden
usarse directamente con el decorador `validated_tool`.
"""
from __future__ import annotations

import functools
import inspect
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, \
    field_validator, model_validator

from app.services import domain

MAX_AMOUNT = 10_000_000.0
GOAL_TARGET_MIN, GOAL_TARGET_MAX = domain.AMOUNT_LIMITS["goal_target"]
MIN_CREDIT_AMOUNT = 1_000.0
MAX_RATE = 200.0
MIN_MONTHS = 3
MAX_MONTHS = 120
MAX_TRANSACTION_LIMIT = 200
MAX_TREND_MONTHS = 24
MAX_WEEKS = 52


def _iso_date(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("La fecha debe usar el formato AAAA-MM-DD.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("La fecha debe usar el formato AAAA-MM-DD.") from exc
    return value


def _deadline(value: str) -> str:
    try:
        validated = domain.validate_deadline(value)
    except domain.DomainError as exc:
        raise ValueError(exc.message) from exc
    if validated is None:
        raise ValueError("La fecha límite no es válida.")
    return validated


def _goal_name(value: str) -> str:
    try:
        return domain.validate_goal_name(value)
    except domain.DomainError as exc:
        raise ValueError(exc.message) from exc


def _month(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("El mes debe usar el formato AAAA-MM.")
    year, month = (int(part) for part in value.split("-"))
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise ValueError("El mes debe estar entre 2000-01 y 2100-12.")
    return value


def _idempotency_key(value: str) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError("La clave de idempotencia debe ser un UUID de 36 caracteres.")
    try:
        uuid.UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("La clave de idempotencia no es un UUID válido.") from exc
    return value


IsoDate = Annotated[str, AfterValidator(_iso_date)]
Deadline = Annotated[str, AfterValidator(_deadline)]
GoalName = Annotated[str, AfterValidator(_goal_name)]
Month = Annotated[str, AfterValidator(_month)]
IdempotencyKey = Annotated[str, AfterValidator(_idempotency_key)]


class ToolInput(BaseModel):
    """Base estricta para los argumentos de una herramienta MCP."""

    model_config = ConfigDict(extra="forbid")

    def model_dump_one_level(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for name, info in self.__class__.model_fields.items():
            output_name = info.alias or name
            kwargs[output_name] = getattr(self, name)
        return kwargs


class NoArgumentsInput(ToolInput):
    pass


class GetTransactionsInput(ToolInput):
    date_from: IsoDate | None = None
    date_to: IsoDate | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    tx_type: Literal["income", "expense", "transfer"] | None = None
    q: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=50, ge=1, le=MAX_TRANSACTION_LIMIT)

    @model_validator(mode="after")
    def _validate_dates(self):
        if (self.date_from is None) != (self.date_to is None):
            raise ValueError("date_from y date_to deben enviarse juntos.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from no puede ser posterior a date_to.")
        return self


class AnalyzeSpendingInput(ToolInput):
    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    date_from: IsoDate | None = None
    date_to: IsoDate | None = None

    @model_validator(mode="after")
    def _validate_dates(self):
        if (self.date_from is None) != (self.date_to is None):
            raise ValueError("date_from y date_to deben enviarse juntos.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from no puede ser posterior a date_to.")
        return self


class CalculateCreditSimulationInput(ToolInput):
    amount: float = Field(ge=MIN_CREDIT_AMOUNT, le=MAX_AMOUNT)
    months: int = Field(ge=MIN_MONTHS, le=MAX_MONTHS)
    annual_rate: float = Field(ge=0, le=MAX_RATE)
    method: Literal["frances", "aleman"] = "frances"


class PeriodInput(ToolInput):
    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)


class GetSpendingTrendInput(ToolInput):
    months: int = Field(default=4, ge=1, le=MAX_TREND_MONTHS)
    category: str | None = Field(default=None, min_length=1, max_length=80)


class CompareMonthsInput(ToolInput):
    month_a: Month
    month_b: Month


class GetWeeklySpendingInput(ToolInput):
    weeks: int = Field(default=4, ge=1, le=MAX_WEEKS)


class ProjectSavingsInput(ToolInput):
    monthly_amount: float = Field(gt=0, le=MAX_AMOUNT)
    target_amount: float = Field(gt=0, le=MAX_AMOUNT)
    already_saved: float = Field(default=0, ge=0, le=MAX_AMOUNT)


class CompareCreditTermsInput(ToolInput):
    amount: float = Field(ge=MIN_CREDIT_AMOUNT, le=MAX_AMOUNT)
    terms: list[int] | None = Field(default=None, max_length=12)
    annual_rate: float = Field(default=15.9, ge=0, le=MAX_RATE)

    @field_validator("terms")
    @classmethod
    def _validate_terms(cls, value):
        if value is None:
            return None
        for term in value:
            if not (MIN_MONTHS <= term <= MAX_MONTHS):
                raise ValueError("Cada plazo debe estar entre 3 y 120 meses.")
        return value


class CreateSavingsGoalInput(ToolInput):
    name: GoalName
    target_amount: float = Field(ge=GOAL_TARGET_MIN, le=GOAL_TARGET_MAX)
    deadline: Deadline | None = None
    confirm: bool = False
    idempotency_key: IdempotencyKey | None = None


class UpdateSavingsGoalInput(ToolInput):
    goal_id: int = Field(gt=0)
    name: GoalName | None = None
    target_amount: float | None = Field(
        default=None, ge=GOAL_TARGET_MIN, le=GOAL_TARGET_MAX,
    )
    deadline: Deadline | None = None
    confirm: bool = False


class ApplySavingsContributionInput(ToolInput):
    goal_id: int | None = Field(default=None, gt=0)
    amount: float = Field(gt=0, le=MAX_AMOUNT)
    confirm: bool = False
    idempotency_key: IdempotencyKey | None = None
    goal_name: GoalName | None = None

    @model_validator(mode="after")
    def _validate_goal_reference(self):
        if self.goal_id is None and not self.goal_name:
            raise ValueError("Indica goal_id o goal_name para identificar la meta.")
        return self


ToolRisk = Literal["read", "write", "sensitive", "destructive"]
IdempotencyMode = Literal["none", "optional", "required"]


@dataclass(frozen=True)
class ToolContract:
    name: str
    title: str
    description: str
    input_model: type[ToolInput]
    risk: ToolRisk
    permissions: tuple[str, ...]
    audit_event: str
    output_contract: str
    requires_confirmation: bool = False
    idempotency: IdempotencyMode = "none"
    sensitive_output: bool = False
    returns_no_data: bool = False

    @property
    def is_write(self) -> bool:
        return self.risk in ("write", "destructive")

    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


def _contract(name: str, title: str, description: str, input_model: type[ToolInput],
              *, risk: ToolRisk = "read", permissions: tuple[str, ...] = ("finance:read",),
              output_contract: str, requires_confirmation: bool = False,
              idempotency: IdempotencyMode = "none", sensitive_output: bool = False,
              returns_no_data: bool = False) -> ToolContract:
    return ToolContract(
        name=name,
        title=title,
        description=description,
        input_model=input_model,
        risk=risk,
        permissions=permissions,
        audit_event=f"mcp_{name}",
        output_contract=output_contract,
        requires_confirmation=requires_confirmation,
        idempotency=idempotency,
        sensitive_output=sensitive_output,
        returns_no_data=returns_no_data,
    )


CATALOG: tuple[ToolContract, ...] = (
    _contract(
        "get_balance", "Saldo disponible",
        "Consulta el saldo total y las cuentas de demostración. Úsala para saber "
        "cuánto dinero hay disponible; no mueve dinero ni calcula proyecciones. "
        "Devuelve importes en MXN y la lista de cuentas; si no hay cuentas, "
        "devuelve una lista vacía declarada por la herramienta.",
        NoArgumentsInput,
        permissions=("finance:read",),
        output_contract="Saldo total y cuentas en MXN; base: saldo en cuentas.",
        returns_no_data=True,
    ),
    _contract(
        "get_transactions", "Movimientos",
        "Consulta movimientos con filtros opcionales por fecha, categoría, tipo "
        "y texto. Úsala para listar o buscar movimientos; no sirve para agregados "
        "ni para escribir. Devuelve importes en MXN, el periodo solicitado y el "
        "conteo total.",
        GetTransactionsInput,
        permissions=("transactions:read",),
        output_contract="Movimientos en MXN con filtros y periodo declarados.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "get_cards", "Tarjetas",
        "Consulta las tarjetas de demostración. Solo expone datos no sensibles, "
        "como los últimos cuatro dígitos; nunca devuelve números completos ni CVV. "
        "Úsala para mostrar tarjetas, no para validar datos reales.",
        NoArgumentsInput,
        permissions=("cards:read",),
        output_contract="Tarjetas ficticias con últimos cuatro dígitos; sin CVV.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "get_savings_goals", "Metas de ahorro",
        "Obtiene las metas de ahorro y su progreso. Úsala para consultar metas o "
        "preparar una aportación; no escribe. Devuelve importes en MXN, porcentaje "
        "con base en el objetivo de cada meta y su estado.",
        NoArgumentsInput,
        permissions=("savings:read",),
        output_contract="Metas con objetivo, ahorrado y avance; base: objetivo de la meta.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "create_savings_goal", "Crear meta de ahorro",
        "Crea una meta de ahorro. Sin confirm=True devuelve requires_confirmation "
        "y no escribe; con confirm=True escribe una sola vez. Usa idempotency_key "
        "para reintentos seguros. No mueve dinero real. Devuelve la meta creada en MXN.",
        CreateSavingsGoalInput,
        risk="write",
        permissions=("savings:write",),
        output_contract="Meta creada con objetivo y ahorrado en MXN; estado created.",
        requires_confirmation=True,
        idempotency="optional",
    ),
    _contract(
        "update_savings_goal", "Actualizar meta de ahorro",
        "Actualiza los datos declarativos de una meta existente. Sin confirm=True "
        "devuelve requires_confirmation y no escribe; con confirm=True escribe. "
        "No permite cambiar el ahorrado ni el estado mediante esta herramienta.",
        UpdateSavingsGoalInput,
        risk="write",
        permissions=("savings:write",),
        output_contract="Meta actualizada con objetivo y ahorrado en MXN; estado updated.",
        requires_confirmation=True,
    ),
    _contract(
        "apply_savings_contribution", "Aportar a una meta",
        "Aplica una transferencia confirmada de una cuenta a una meta. Requiere "
        "confirm=True e idempotency_key; valida el disponible y lo que falta en la "
        "capa de dominio. No registra un gasto ni mueve dinero real. Devuelve el "
        "movimiento y los saldos resultantes en MXN.",
        ApplySavingsContributionInput,
        risk="write",
        permissions=("savings:write", "transactions:write"),
        output_contract="Transferencia aplicada, meta y saldos en MXN; estado applied.",
        requires_confirmation=True,
        idempotency="required",
    ),
    _contract(
        "analyze_spending", "Análisis de gastos",
        "Analiza gastos por categoría en un mes o en un rango de fechas. Úsala para "
        "entender la composición del gasto; no incluye ingresos ni transferencias. "
        "Devuelve importes en MXN, periodo y porcentajes con base en el total de gastos.",
        AnalyzeSpendingInput,
        permissions=("analytics:read",),
        output_contract="Gasto por categoría en MXN; base: total de gastos del periodo.",
        returns_no_data=True,
    ),
    _contract(
        "calculate_credit_simulation", "Simular crédito",
        "Calcula una simulación educativa de crédito con método francés o alemán. "
        "Úsala para estimar cuota e intereses; no es una oferta ni una aprobación. "
        "Devuelve importes en MXN, tasa anual y tabla de amortización.",
        CalculateCreditSimulationInput,
        permissions=("credit:simulate",),
        output_contract="Cuota, intereses y tabla en MXN; tasa anual declarada.",
    ),
    _contract(
        "get_monthly_summary", "Resumen mensual",
        "Obtiene ingresos, gastos, balance y principales categorías de un mes. Úsala "
        "para un resumen; no sustituye el detalle de movimientos. Devuelve importes "
        "en MXN y el periodo consultado.",
        PeriodInput,
        permissions=("analytics:read",),
        output_contract="Ingresos, gastos, balance y top categorías en MXN; periodo declarado.",
        returns_no_data=True,
    ),
    _contract(
        "get_budgets", "Presupuesto",
        "Consulta el presupuesto del mes con gasto real contra límites configurados. "
        "Úsala para revisar límites; no los modifica. Devuelve importes en MXN, "
        "porcentaje con base en el límite y el periodo.",
        PeriodInput,
        permissions=("budget:read",),
        output_contract="Gasto y límite por categoría en MXN; base: límite configurado.",
        returns_no_data=True,
    ),
    _contract(
        "get_spending_trend", "Tendencia de gasto",
        "Consulta la tendencia de gasto de los últimos meses, opcionalmente por "
        "categoría. Úsala para comparar evolución; no proyecta a futuro. Devuelve "
        "importes en MXN, meses y cambio porcentual con base en el primer mes.",
        GetSpendingTrendInput,
        permissions=("analytics:read",),
        output_contract="Serie mensual de gasto en MXN; cambio con base en el primer mes.",
        returns_no_data=True,
    ),
    _contract(
        "compare_months", "Comparar meses",
        "Compara dos meses en ingresos, gastos y balance. Úsala para diferencias "
        "entre periodos; no mezcla categorías. Devuelve importes en MXN y ambos "
        "periodos declarados.",
        CompareMonthsInput,
        permissions=("analytics:read",),
        output_contract="Resúmenes de dos meses y diferencia de gasto en MXN; periodos declarados.",
        returns_no_data=True,
    ),
    _contract(
        "get_weekly_spending", "Gasto semanal",
        "Obtiene el gasto total por semana de las últimas N semanas. Úsala para "
        "ritmo semanal; no sustituye el detalle diario. Devuelve importes en MXN y "
        "la serie semanal.",
        GetWeeklySpendingInput,
        permissions=("analytics:read",),
        output_contract="Gasto por semana en MXN; serie y número de semanas declarados.",
        returns_no_data=True,
    ),
    _contract(
        "detect_recurring_charges", "Cargos recurrentes",
        "Detecta cargos fijos o recurrentes, como suscripciones y pagos mensuales. "
        "Úsala para identificar compromisos; no confirma que sean obligatorios. "
        "Devuelve cargos y total mensual estimado en MXN.",
        NoArgumentsInput,
        permissions=("analytics:read",),
        output_contract="Cargos recurrentes y total mensual estimado en MXN.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "detect_duplicates", "Cobros duplicados",
        "Detecta cobros duplicados del mismo cargo el mismo día. Úsala para revisar "
        "posibles cargos repetidos; no reembolsa ni corrige movimientos. Devuelve "
        "los grupos detectados en MXN.",
        NoArgumentsInput,
        permissions=("analytics:read",),
        output_contract="Grupos de cobros duplicados en MXN; sin acciones de escritura.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "detect_anomalies", "Cargos inusuales",
        "Detecta cargos inusualmente altos para su categoría, excluyendo recurrentes "
        "y duplicados. Úsala para señalar posibles anomalías; no bloquea ni revierte "
        "cargos. Devuelve los cargos y su referencia en MXN.",
        NoArgumentsInput,
        permissions=("analytics:read",),
        output_contract="Cargos anómalos en MXN; referencia por categoría y periodo.",
        sensitive_output=True,
        returns_no_data=True,
    ),
    _contract(
        "project_savings", "Proyección de ahorro",
        "Proyecta cuántos meses faltan para una meta con un ahorro mensual dado. "
        "Úsala para planear; no crea ni modifica metas. Devuelve meses, importes en "
        "MXN y declara si la meta ya se alcanzó.",
        ProjectSavingsInput,
        permissions=("savings:read",),
        output_contract="Meses necesarios e importes en MXN; base: ahorro mensual y objetivo.",
    ),
    _contract(
        "compare_credit_terms", "Comparar plazos de crédito",
        "Compara plazos de crédito para un monto y una tasa anual. Úsala para "
        "contrastar cuotas; no es una oferta. Devuelve cuota, intereses y total por "
        "plazo en MXN.",
        CompareCreditTermsInput,
        permissions=("credit:simulate",),
        output_contract="Cuota, intereses y total por plazo en MXN; tasa anual declarada.",
    ),
    _contract(
        "budget_vs_actual", "Presupuesto contra real",
        "Compara el presupuesto planeado contra el gasto real y señala categorías "
        "excedidas. Úsala para seguimiento; no modifica límites. Devuelve importes "
        "en MXN, porcentaje con base en el límite y el periodo.",
        PeriodInput,
        permissions=("budget:read",),
        output_contract="Presupuesto y gasto real por categoría en MXN; base: límite configurado.",
        returns_no_data=True,
    ),
)

TOOL_BY_NAME: dict[str, ToolContract] = {contract.name: contract for contract in CATALOG}
MCP_ALLOWED_TOOLS = frozenset(TOOL_BY_NAME)
READ_TOOLS = frozenset(c.name for c in CATALOG if c.risk == "read")
WRITE_TOOLS = frozenset(c.name for c in CATALOG if c.is_write)
SENSITIVE_TOOLS = frozenset(c.name for c in CATALOG if c.sensitive_output)
DESTRUCTIVE_TOOLS = frozenset(c.name for c in CATALOG if c.risk == "destructive")

if len(TOOL_BY_NAME) != len(CATALOG):  # pragma: no cover - fallo de importación
    raise RuntimeError("El catálogo MCP tiene nombres duplicados.")


class ToolValidationError(ValueError):
    """Error de validación de argumentos con nombre de herramienta."""

    def __init__(self, tool: str, message: str) -> None:
        super().__init__(f"Argumentos inválidos para '{tool}': {message}")
        self.tool = tool


def sin_dato(code: str, message: str, *, period: str | None = None) -> dict[str, Any]:
    """Estado vacío tipado y estable para las herramientas que lo declaran."""
    return {"code": code, "message": message, "period": period}


def add_sin_dato(payload: dict[str, Any], empty: bool, code: str, message: str,
                 *, period: str | None = None) -> dict[str, Any]:
    if empty:
        payload["sin_dato"] = sin_dato(code, message, period=period)
    return payload


def get_contract(name: str) -> ToolContract | None:
    return TOOL_BY_NAME.get(name)


def _format_validation_error(name: str, exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(item) for item in error.get("loc", ())) or "argumentos"
        parts.append(f"{location}: {error.get('msg', 'valor inválido')}")
    return "; ".join(parts)


def validate_arguments(name: str, arguments: dict[str, Any] | None) -> ToolInput:
    contract = get_contract(name)
    if contract is None:
        raise ToolValidationError(name, "herramienta desconocida.")
    try:
        return contract.input_model.model_validate(arguments or {})
    except ValidationError as exc:
        raise ToolValidationError(name, _format_validation_error(name, exc)) from exc


def validated_tool(name: str):
    """Valida argumentos antes de ejecutar una implementación directa."""
    contract = get_contract(name)
    if contract is None:
        raise KeyError(f"Herramienta sin contrato: {name}")

    def decorator(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            validated = validate_arguments(name, dict(bound.arguments))
            return await fn(**validated.model_dump_one_level())

        return wrapper

    return decorator


def catalog_snapshot() -> list[dict[str, Any]]:
    """Vista serializable del catálogo para pruebas y documentación."""
    return [
        {
            "name": contract.name,
            "title": contract.title,
            "description": contract.description,
            "risk": contract.risk,
            "permissions": list(contract.permissions),
            "requires_confirmation": contract.requires_confirmation,
            "idempotency": contract.idempotency,
            "sensitive_output": contract.sensitive_output,
            "returns_no_data": contract.returns_no_data,
            "input_schema": contract.input_schema(),
            "output_contract": contract.output_contract,
        }
        for contract in CATALOG
    ]
