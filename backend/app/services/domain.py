"""Capa única de dominio: autoridad de invariantes y validación de entradas.

Ninguna otra parte del sistema define límites de importe, reglas de fecha,
longitud de nombres ni cotas de ahorro. La API REST y el servidor MCP invocan
**estas** funciones (INV-9).

Relación con `finance.py`:
- `finance.py` es la autoridad de **métricas derivadas** (saldos, agregados).
- `domain.py` es la autoridad de **reglas** y consulta a `finance` para
  conocer el estado (disponible, ahorrado). La dependencia va en un solo
  sentido: `domain` conoce a `finance`, nunca al revés.
"""
from __future__ import annotations

import math
from datetime import date

from app.core import money
from app.services import finance

# ------------------------------------------------------------------ contrato

# Una sola definición de los sentidos válidos (vive con el libro, en finance).
TRANSFER_DIRECTIONS = finance.TRANSFER_DIRECTIONS

# Límites de importe: una sola definición por tipo de operación.
AMOUNT_LIMITS: dict[str, tuple[float, float]] = {
    "goal_target": (1.0, 100_000_000.0),
    "income": (0.01, 1_000_000_000.0),
    "expense": (0.01, 1_000_000_000.0),
    "transfer": (0.01, 1_000_000_000.0),
}

GOAL_NAME_MIN = 2
GOAL_NAME_MAX = 80


class DomainError(ValueError):
    """Error de dominio con código estable y mensaje para la persona.

    `code` permite que la UI reaccione sin volver a decidir la regla; el
    mensaje es el texto que se le explica a la persona.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ------------------------------------------------------------- importes

def validate_amount(value, *, kind: str) -> float:
    """Valida un importe según su tipo y lo normaliza a 2 decimales.

    Rechaza valores no numéricos, no finitos, cero, negativos o fuera del
    rango declarado para `kind` (INV-4, Clase D). La normalización es la
    canónica del módulo `money` (único punto de conversión).
    """
    if kind not in AMOUNT_LIMITS:
        raise DomainError("amount_unknown_kind", f"Tipo de importe desconocido: {kind}.")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainError("amount_not_a_number", "El monto debe ser un número.")
    amount = float(value)
    if not math.isfinite(amount):
        raise DomainError("amount_not_finite", "El monto no es un número válido.")
    lo, hi = AMOUNT_LIMITS[kind]
    if amount <= 0:
        raise DomainError("amount_not_positive", "El monto debe ser mayor que cero.")
    if amount < lo or amount > hi:
        raise DomainError(
            "amount_out_of_range",
            f"El monto debe estar entre ${lo:,.2f} y ${hi:,.2f}.",
        )
    return money.boundary(amount)


def validate_money_range(value, *, lo: float, hi: float, label: str) -> float:
    """Valida que un importe esté dentro de un rango explícito."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainError("amount_not_a_number", f"{label} debe ser un número.")
    amount = float(value)
    if not math.isfinite(amount):
        raise DomainError("amount_not_finite", f"{label} no es un número válido.")
    if amount < lo or amount > hi:
        raise DomainError(
            "amount_out_of_range",
            f"{label} debe estar entre ${lo:,.2f} y ${hi:,.2f}.",
        )
    return money.boundary(amount)


# ------------------------------------------------------------- nombres

def validate_goal_name(conn, name) -> str:
    """Sanea y valida el nombre de una meta: longitud, contenido y unicidad.

    La unicidad se comprueba sobre los nombres existentes sin distinguir
    mayúsculas ni espacios repetidos. Es la única definición de esta regla.
    """
    clean = " ".join(str(name or "").split())
    if not (GOAL_NAME_MIN <= len(clean) <= GOAL_NAME_MAX):
        raise DomainError(
            "goal_name_length",
            f"El nombre debe tener entre {GOAL_NAME_MIN} y {GOAL_NAME_MAX} caracteres.",
        )
    existing = {
        " ".join(row["name"].split()).casefold()
        for row in conn.execute("SELECT name FROM savings_goals")
    }
    if clean.casefold() in existing:
        raise DomainError(
            "goal_name_duplicate",
            f"Ya tienes una meta llamada '{clean}'. Elige otro nombre.",
        )
    return clean


# ------------------------------------------------------------- fechas

def validate_deadline(value) -> str | None:
    """Valida una fecha límite: ISO real y no pasada (INV-8, Clase D)."""
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise DomainError("deadline_not_a_date", "La fecha límite no es válida.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DomainError(
            "deadline_not_a_date",
            "La fecha límite no es válida; usa el formato AAAA-MM-DD.",
        ) from exc
    if parsed < date.today():
        raise DomainError(
            "deadline_in_the_past",
            "La fecha límite no puede estar en el pasado.",
        )
    return parsed.isoformat()


# ------------------------------------------------------------- periodos

def period_state(year: int, month: int) -> str:
    """Estado de un periodo: 'en_curso' | 'cerrado' | 'futuro' (INV-8)."""
    if not isinstance(year, int) or not isinstance(month, int) or not (1 <= month <= 12):
        raise DomainError("period_invalid", "El periodo no es válido.")
    today = date.today()
    if (year, month) == (today.year, today.month):
        return "en_curso"
    if (year, month) > (today.year, today.month):
        return "futuro"
    return "cerrado"


def assert_period_has_data(conn, year: int, month: int) -> str:
    """Declara el estado del periodo y exige que tenga datos (INV-6, INV-8).

    Un periodo futuro o sin movimientos se **declara** con un error tipado;
    nunca se sustituye en silencio por el mes en curso.
    """
    state = period_state(year, month)
    if state == "futuro":
        raise DomainError(
            "period_in_future",
            f"El periodo {year}-{month:02d} todavía no ha ocurrido; no hay datos.",
        )
    date_from, date_to = finance.month_range(year, month)
    count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE date >= ? AND date <= ?",
        (date_from, date_to),
    ).fetchone()[0]
    if not count:
        raise DomainError(
            "period_without_data",
            f"No hay movimientos registrados en {year}-{month:02d}.",
        )
    return state


# ------------------------------------------------------------- transferencias

def validate_transfer(conn, *, goal_id, amount: float, direction: str) -> dict:
    """Valida una transferencia cuenta↔meta contra INV-3 e INV-4.

    Devuelve la meta afectada para que el llamador no vuelva a consultarla.
    Aportación (`account_to_goal`): el monto no excede lo que falta para el
    objetivo ni el disponible (saldo en cuentas).
    Retiro (`goal_to_account`): el monto no excede lo ahorrado en la meta.

    La comparación ocurre en centavos exactos; los mensajes se formatean en
    pesos con la conversión única de `money`.
    """
    if direction not in TRANSFER_DIRECTIONS:
        raise DomainError(
            "transfer_bad_direction",
            "La transferencia debe indicar si es una aportación o un retiro.",
        )
    amount = validate_amount(amount, kind="transfer")
    row = conn.execute(
        "SELECT id, name, target_amount_cents, saved_amount_cents"
        " FROM savings_goals WHERE id=?",
        (goal_id,),
    ).fetchone()
    if row is None:
        raise DomainError("goal_not_found", "No encontré esa meta de ahorro.")
    amount_cents = money.to_cents(amount)

    if direction == "account_to_goal":
        missing_cents = max(0, row["target_amount_cents"] - row["saved_amount_cents"])
        if missing_cents <= 0:
            raise DomainError(
                "goal_already_complete",
                f"La meta '{row['name']}' ya alcanzó su objetivo de "
                f"${money.to_pesos(row['target_amount_cents']):,.2f}.",
            )
        if amount_cents > missing_cents:
            raise DomainError(
                "contribution_exceeds_missing",
                f"El abono no puede superar lo que falta para '{row['name']}': "
                f"${money.to_pesos(missing_cents):,.2f}.",
            )
        available_cents = finance.accounts_balance_cents(conn)
        if amount_cents > available_cents:
            raise DomainError(
                "contribution_exceeds_available",
                f"El abono supera tu saldo disponible de "
                f"${money.to_pesos(available_cents):,.2f}.",
            )
    else:  # goal_to_account
        if amount_cents > row["saved_amount_cents"]:
            raise DomainError(
                "withdrawal_exceeds_saved",
                f"El retiro no puede superar lo ahorrado en '{row['name']}': "
                f"${money.to_pesos(row['saved_amount_cents']):,.2f}.",
            )
    return {
        "id": row["id"],
        "name": row["name"],
        "target_amount": money.to_pesos(row["target_amount_cents"]),
        "saved_amount": money.to_pesos(row["saved_amount_cents"]),
    }
