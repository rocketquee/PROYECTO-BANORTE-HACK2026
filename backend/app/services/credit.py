"""Credit simulation engine (educational prototype).

Two classic amortization methods:
- "frances" (French / annuity): fixed payment.
- "aleman" (German / linear): fixed principal, declining interest.

This is NOT an official Banorte product and does not imply any real offer,
rate or approval.
"""

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


def _frances_schedule(amount: float, months: int, monthly_rate: float) -> tuple[float, list[dict]]:
    payment = amount * monthly_rate / (1 - (1 + monthly_rate) ** (-months)) if monthly_rate else amount / months
    schedule, balance = [], amount
    for n in range(1, months + 1):
        interest = balance * monthly_rate
        principal = payment - interest
        balance = max(balance - principal, 0.0)
        schedule.append({"n": n, "payment": round(payment, 2), "interest": round(interest, 2),
                         "principal": round(principal, 2), "balance": round(balance, 2)})
    return payment, schedule


def _aleman_schedule(amount: float, months: int, monthly_rate: float) -> tuple[float, list[dict]]:
    principal = amount / months
    schedule, balance = [], amount
    for n in range(1, months + 1):
        interest = balance * monthly_rate
        payment = principal + interest
        balance = max(balance - principal, 0.0)
        schedule.append({"n": n, "payment": round(payment, 2), "interest": round(interest, 2),
                         "principal": round(principal, 2), "balance": round(balance, 2)})
    return schedule[0]["payment"], schedule


def simulate_credit(amount: float, months: int, annual_rate: float, method: str = "frances") -> dict:
    validate_inputs(amount, months, annual_rate, method)
    monthly_rate = annual_rate / 100 / 12
    if method == "frances":
        payment, schedule = _frances_schedule(amount, months, monthly_rate)
    else:
        payment, schedule = _aleman_schedule(amount, months, monthly_rate)
    total_paid = round(sum(r["payment"] for r in schedule), 2)
    total_interest = round(total_paid - amount, 2)
    return {
        "amount": round(amount, 2),
        "months": months,
        "annual_rate": annual_rate,
        "method": method,
        "monthly_payment": round(payment, 2),
        "total_interest": total_interest,
        "total_paid": total_paid,
        "schedule": schedule,
        "disclaimer": ("Simulación educativa con datos de demostración. No es una oferta oficial "
                       "de crédito de Banorte ni implica aprobación o tasas reales."),
    }
