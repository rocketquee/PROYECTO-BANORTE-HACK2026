"""Representación única del dinero: enteros en centavos (decisión aprobada).

Reglas del contrato monetario (documentadas aquí y en docs/DATA-DICTIONARY.md):

1. **Almacenamiento**: todo importe en la base es `INTEGER` de centavos
   (`*_cents`). Prohibido `REAL`/`float` para dinero en disco.
2. **Conversión**: este módulo es el **único** punto que convierte entre
   pesos (flotante de la API/interfaz) y centavos (entero de la base).
   Ninguna otra capa multiplica ni divide por 100.
3. **Redondeo**: `ROUND_HALF_UP` (medio peso/arriba), con `Decimal`, nunca
   flotantes. Aplica a intereses, cuotas y porcentajes.
4. **Porcentajes** (INV-7): `pct()` calcula sobre centavos y redondea a
   1 decimal con `ROUND_HALF_UP`. La base del porcentaje viaja junto al valor.
5. **Amortización**: los intereses de cada cuota se redondean al centavo
   (`apply_rate`); la **última cuota absorbe el residuo** para que la suma de
   capital sea exactamente el monto prestado y la suma de pagos cierre la
   operación sin diferencia.
6. **Repartos**: `split_evenly` reparte un total en `n` partes iguales en
   centavos; la última parte absorbe el residuo.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CENT = Decimal("0.01")


class MoneyError(ValueError):
    """Valor monetario no representable (no finito, no numérico, negativo…)."""


def to_cents(value) -> int:
    """Pesos (int/float/str/Decimal) → centavos enteros con `ROUND_HALF_UP`.

    Es la única puerta de entrada al libro. Rechaza `bool`, no numéricos,
    no finitos y negativos (el dinero del libro es positivo; los signos se
    expresan por tipo de movimiento).
    """
    if isinstance(value, bool):
        raise MoneyError("El monto debe ser un número.")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MoneyError("El monto debe ser un número.") from exc
    if not dec.is_finite():
        raise MoneyError("El monto no es un número válido.")
    cents = dec.quantize(_CENT, rounding=ROUND_HALF_UP) * 100
    result = int(cents)
    if result < 0:
        raise MoneyError("El monto no puede ser negativo.")
    return result


def to_pesos(cents: int) -> float:
    """Centavos enteros → pesos (flotante con 2 decimales exactos).

    Solo para la **frontera** (respuestas API/interfaz). La división por 100
    produce el flotante más cercano al valor decimal de 2 dígitos, que es
    exactamente el valor que la API siempre emitió.
    """
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise MoneyError("Los centavos deben ser un entero.")
    return cents / 100


def boundary(value) -> float:
    """Normaliza un importe de entrada a la forma canónica de la API.

    `float` de la interfaz → centavos → `float` de 2 decimales. Sustituye a
    los `round(x, 2)` defensivos: la normalización vive aquí, una vez.
    """
    return to_pesos(to_cents(value))


def _to_cents_signed(value) -> int:
    """Conversión con signo: acepta importes negativos (diferencias netas)."""
    if isinstance(value, bool):
        raise MoneyError("El monto debe ser un número.")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MoneyError("El monto debe ser un número.") from exc
    if not dec.is_finite():
        raise MoneyError("El monto no es un número válido.")
    return int(dec.quantize(_CENT, rounding=ROUND_HALF_UP) * 100)


#: Conversión con signo para agregados que pueden ser negativos (netos,
#: diferencias). Los importes del libro usan `to_cents`, que exige positivos.
to_cents_signed = _to_cents_signed


def difference(a, b) -> float:
    """Resta exacta de dos importes en pesos, vía centavos.

    Acepta resultados negativos (p. ej. un balance mensual negativo); la
    resta ocurre en centavos enteros y el resultado vuelve a la forma
    canónica de la API.
    """
    return to_pesos(_to_cents_signed(a) - _to_cents_signed(b))


def round_half_up(value) -> int:
    """Redondea un número (típicamente centavos fraccionarios) al entero más
    cercano con `ROUND_HALF_UP`. Es el redondeo oficial del sistema."""
    if isinstance(value, Decimal):
        dec = value
    else:
        dec = Decimal(str(value))
    if not dec.is_finite():
        raise MoneyError("El valor no es un número válido.")
    return int(dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def apply_rate(cents: int, rate: float) -> int:
    """Interés de un periodo: `centavos × tasa`, redondeado al centavo.

    `rate` es una **tasa**, no dinero (p. ej. 0.01 = 1 % mensual). La
    multiplicación centavos×tasa es exacta en Decimal; el único redondeo es
    el centavo final con `ROUND_HALF_UP`.
    """
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise MoneyError("Los centavos deben ser un entero.")
    return round_half_up(Decimal(cents) * Decimal(str(rate)))


def monthly_rate(annual_rate) -> float:
    """Tasa anual (%) → tasa mensual fraccional. Única definición
    (`anual / 1200`); las tasas no son dinero y viven en flotante."""
    value = float(annual_rate)
    if value != value or value in (float("inf"), float("-inf")):
        raise MoneyError("La tasa no es un número válido.")
    return value / 1200


def pct(part_cents: int, whole_cents: int, ndigits: int = 1) -> float:
    """Porcentaje (INV-7) sobre centavos, con `ROUND_HALF_UP` a `ndigits`.

    Devuelve el porcentaje como flotante de presentación; la base exacta
    (`whole_cents`) viaja en la respuesta como `pct_base_value`.
    """
    if whole_cents == 0:
        return 0.0
    value = Decimal(part_cents) * 100 / Decimal(whole_cents)
    quantum = Decimal(1).scaleb(-ndigits)
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))


def split_evenly(total_cents: int, parts: int) -> list[int]:
    """Reparte `total_cents` en `parts` cuotas iguales; la última absorbe el
    residuo para que la suma sea **exactamente** el total."""
    if parts <= 0:
        raise MoneyError("El número de partes debe ser positivo.")
    if total_cents < 0:
        raise MoneyError("El total no puede ser negativo.")
    base = total_cents // parts
    shares = [base] * parts
    shares[-1] += total_cents - base * parts
    return shares
