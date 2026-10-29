"""Credit simulation engine (educational prototype).

Two classic amortization methods:
- "frances" (French / annuity): fixed payment.
- "aleman" (German / linear): fixed principal, declining interest.

Dinero: la tabla de amortización se calcula **en centavos enteros** con las
reglas de `app.core.money`:

- El interés de cada cuota es `apply_rate(saldo, tasa)` → `ROUND_HALF_UP` al
  centavo.
- La **última cuota absorbe el residuo**: su capital es el saldo restante, de
  modo que Σ capital = monto exacto y el saldo termina en 0 sin diferencia.
- La respuesta se emite en pesos (frontera de API) con la conversión única.

This is NOT an official Banorte product and does not imply any real offer,
rate or approval.
"""
from decimal import Decimal

from app.core import money

VALID_METHODS = ("frances", "aleman")


def validate_inputs(amount: float, months: int, annual_rate: float, method: str) -> None:
    if not (1_000 <= amount <= 10_000_000):
        raise ValueError("El monto debe estar entre $1,000 y $10,000,000.")
    if not (3 <= months <= 120):
        raise ValueError("El plazo debe estar entre 3 y 120 meses.")
    if not (0 <= annual_rate <= 200):
        raise ValueError("La tasa anual debe estar entre 0 y 200 %.")
    if method not in VALID_METHODS:
        raise ValueError(f"Método no soportado. Use uno de: {', '.join(VALID_METHODS)}.")


def _row(n: int, payment_c: int, interest_c: int, principal_c: int, balance_c: int) -> dict:
    """Frontera centavos→pesos: única salida de las filas de la tabla."""
    return {
        "n": n,
        "payment": money.to_pesos(payment_c),
        "interest": money.to_pesos(interest_c),
        "principal": money.to_pesos(principal_c),
        "balance": money.to_pesos(balance_c),
    }


def _frances_schedule(amount_cents: int, months: int,
                      monthly_rate: float) -> tuple[int, list[dict], int]:
    """Cuota fija. La última cuota absorbe el residuo del capital.

    Devuelve `(cuota, filas_en_pesos, total_pagado_en_centavos)`.
    """
    if monthly_rate:
        raw = Decimal(amount_cents) * Decimal(str(monthly_rate)) / (
            1 - Decimal(1 + monthly_rate) ** Decimal(-months))
        payment_c = money.round_half_up(raw)
    else:
        payment_c = money.split_evenly(amount_cents, months)[0]
    schedule: list[dict] = []
    balance_c = amount_cents
    total_paid_c = 0
    for n in range(1, months + 1):
        interest_c = money.apply_rate(balance_c, monthly_rate) if monthly_rate else 0
        if n == months:
            # Última cuota: el capital restante cierra la operación exacta.
            principal_c = balance_c
            payment_n = principal_c + interest_c
            balance_c = 0
        else:
            principal_c = payment_c - interest_c
            payment_n = payment_c
            balance_c -= principal_c
        total_paid_c += payment_n
        schedule.append(_row(n, payment_n, interest_c, principal_c, max(balance_c, 0)))
    return payment_c, schedule, total_paid_c


def _aleman_schedule(amount_cents: int, months: int,
                     monthly_rate: float) -> tuple[int, list[dict], int]:
    """Capital fijo con residuo absorbido en la última cuota."""
    principal_shares = money.split_evenly(amount_cents, months)
    schedule: list[dict] = []
    balance_c = amount_cents
    total_paid_c = 0
    for n, principal_c in enumerate(principal_shares, start=1):
        interest_c = money.apply_rate(balance_c, monthly_rate) if monthly_rate else 0
        balance_c -= principal_c
        payment_n = principal_c + interest_c
        total_paid_c += payment_n
        schedule.append(_row(n, payment_n, interest_c, principal_c, max(balance_c, 0)))
    first_payment_c = principal_shares[0] + (
        money.apply_rate(amount_cents, monthly_rate) if monthly_rate else 0
    )
    return first_payment_c, schedule, total_paid_c


def simulate_credit(amount: float, months: int, annual_rate: float, method: str = "frances") -> dict:
    validate_inputs(amount, months, annual_rate, method)
    rate = money.monthly_rate(annual_rate)
    amount_cents = money.to_cents(amount)
    if method == "frances":
        payment_c, schedule, total_paid_c = _frances_schedule(amount_cents, months, rate)
    else:
        payment_c, schedule, total_paid_c = _aleman_schedule(amount_cents, months, rate)
    total_interest_c = total_paid_c - amount_cents
    return {
        "amount": money.to_pesos(amount_cents),
        "months": months,
        "annual_rate": annual_rate,
        "method": method,
        "monthly_payment": money.to_pesos(payment_c),
        "total_interest": money.to_pesos(total_interest_c),
        "total_paid": money.to_pesos(total_paid_c),
        "schedule": schedule,
        "disclaimer": ("Simulación educativa con datos de demostración. No es una oferta oficial "
                       "de crédito de Banorte ni implica aprobación o tasas reales."),
    }
