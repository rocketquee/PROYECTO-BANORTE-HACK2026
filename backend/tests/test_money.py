"""Pruebas del módulo único de dinero (D1: centavos enteros).

Regla aprobada: la base almacena centavos (`INTEGER`), la conversión vive
solo en `app.core.money`, y el redondeo oficial es `ROUND_HALF_UP` con la
última cuota de una amortización absorbiendo el residuo.
"""
from decimal import Decimal

import pytest

from app.core import money
from app.services import credit


# ---------------------------------------------------------------- conversión

@pytest.mark.parametrize("pesos,cents", [
    (0, 0),
    (1, 100),
    (1234.56, 123456),
    ("1234.56", 123456),
    (0.1, 10),
    (0.005, 1),        # medio centavo: ROUND_HALF_UP hacia arriba
    (2.675, 268),      # el binario 2.67499… se cuantiza al valor declarado
    (Decimal("99.99"), 9999),
])
def test_to_cents_converts_exactly(pesos, cents):
    assert money.to_cents(pesos) == cents


def test_to_cents_rejects_invalid():
    for bad in (True, False, "abc", float("inf"), float("nan"), None, -1, -0.01):
        with pytest.raises(money.MoneyError):
            money.to_cents(bad)


def test_roundtrip_pesos_cents_pesos_is_exact():
    for cents in (0, 1, 5, 99, 123456, 999999999):
        assert money.to_cents(money.to_pesos(cents)) == cents


def test_boundary_normalizes_noise():
    assert money.boundary(1234.5600000000001) == 1234.56
    assert money.boundary("7") == 7.0


# ---------------------------------------------------------------- redondeo

def test_round_half_up_rule():
    assert money.round_half_up("2.5") == 3      # medio hacia arriba, no al par
    assert money.round_half_up("2.4") == 2
    assert money.round_half_up("-2.5") == -3
    assert money.round_half_up(101.5) == 102


def test_apply_rate_rounds_to_the_cent():
    # 10,000.00 × 1 % mensual = 100.00 exacto.
    assert money.apply_rate(1_000_000, 0.01) == 10_000
    # Saldo impar: 1.23 × 0.5 % = 0.615 → 0.62 (HALF_UP).
    assert money.apply_rate(123, 0.005) == 1


def test_pct_uses_half_up_at_one_decimal():
    # 12.25 % exacto → 12.3 con HALF_UP (el redondeo bancario daría 12.2).
    assert money.pct(49, 400) == 12.3
    assert money.pct(0, 400) == 0.0
    assert money.pct(400, 0) == 0.0


def test_split_evenly_last_share_absorbs_residue():
    shares = money.split_evenly(10_001, 12)
    assert len(shares) == 12
    assert sum(shares) == 10_001           # la suma es exacta
    assert all(s == 833 for s in shares[:-1])
    assert shares[-1] == 833 + 5           # el residuo (5) cayó en la última
    assert money.split_evenly(7, 2) == [3, 4]


def test_monthly_rate_single_definition():
    assert money.monthly_rate(12) == pytest.approx(0.01)
    assert money.monthly_rate(15.9) == pytest.approx(15.9 / 1200)


# ---------------------------------------------------------------- amortización

def _assert_schedule_closes(result, amount):
    schedule = result["schedule"]
    assert sum(r["principal"] for r in schedule) == pytest.approx(amount, abs=0.001)
    assert sum(r["payment"] for r in schedule) == pytest.approx(result["total_paid"], abs=0.001)
    assert schedule[-1]["balance"] == 0


def test_french_schedule_exact_closure_with_residue_on_last_installment():
    result = credit.simulate_credit(100_000, 12, 12.0, "frances")
    assert result["monthly_payment"] == pytest.approx(8_884.88, abs=0.05)
    _assert_schedule_closes(result, 100_000)


def test_german_schedule_exact_closure():
    result = credit.simulate_credit(100_000, 12, 12.0, "aleman")
    first, last = result["schedule"][0], result["schedule"][-1]
    assert first["payment"] > last["payment"]
    assert result["monthly_payment"] == first["payment"]
    _assert_schedule_closes(result, 100_000)


def test_zero_rate_installments_split_evenly():
    result = credit.simulate_credit(120_000, 12, 0.0, "frances")
    assert result["monthly_payment"] == 10_000
    assert result["total_interest"] == 0
    _assert_schedule_closes(result, 120_000)
