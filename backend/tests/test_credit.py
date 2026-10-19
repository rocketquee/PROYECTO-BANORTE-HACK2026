import pytest

from app.services.credit import simulate_credit


def test_french_annuity_known_value():
    """$100,000, 12 meses, 12% anual → mensualidad ≈ $8,884.88."""
    result = simulate_credit(100_000, 12, 12.0, "frances")
    assert result["monthly_payment"] == pytest.approx(8_884.88, abs=0.05)
    assert result["total_paid"] > 100_000
    assert result["total_interest"] == pytest.approx(result["total_paid"] - 100_000, abs=0.01)
    assert len(result["schedule"]) == 12
    # balance ends at ~0
    assert result["schedule"][-1]["balance"] == pytest.approx(0, abs=1.0)


def test_german_method_first_payment_higher_than_last():
    result = simulate_credit(100_000, 12, 12.0, "aleman")
    first, last = result["schedule"][0], result["schedule"][-1]
    assert first["payment"] == pytest.approx(100_000 / 12 + 1_000, abs=0.05)
    assert first["payment"] > last["payment"]
    assert result["monthly_payment"] == first["payment"]


def test_zero_rate():
    result = simulate_credit(120_000, 12, 0.0, "frances")
    assert result["monthly_payment"] == pytest.approx(10_000, abs=0.01)
    assert result["total_interest"] == 0


def test_validation_errors():
    with pytest.raises(ValueError):
        simulate_credit(500, 12, 10)          # amount too low
    with pytest.raises(ValueError):
        simulate_credit(100_000, 2, 10)       # months too low
    with pytest.raises(ValueError):
        simulate_credit(100_000, 12, 500)     # rate too high
    with pytest.raises(ValueError):
        simulate_credit(100_000, 12, 10, "inventado")
