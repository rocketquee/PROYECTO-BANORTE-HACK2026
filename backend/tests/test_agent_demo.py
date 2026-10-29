import pytest

from app.services.agent.orchestrator import detect_intent, extract_amount


@pytest.mark.parametrize("text,expected", [
    ("¿En qué estoy gastando más dinero?", "spending"),
    ("Analiza mis gastos de este mes", "spending"),
    ("Ayúdame a ahorrar $5,000", "savings"),
    ("Quiero crear una meta de ahorro", "savings"),
    ("¿Cuánto podría pagar mensualmente por un crédito?", "credit"),
    ("Simula un préstamo de 100 mil", "credit"),
    ("Muéstrame mis movimientos y clasifícalos", "movements"),
    ("¿Cómo puedo organizar mi presupuesto?", "budget"),
    ("¿Cuál es mi saldo actual?", "overview"),
    ("hola", "greeting"),
])
def test_detect_intent(text, expected):
    assert detect_intent(text) == expected


def test_extract_amount():
    assert extract_amount("ayúdame a ahorrar $5,000") == 5000
    assert extract_amount("ahorrar 8000 pesos") == 8000
    assert extract_amount("simula un crédito de $250,000") == 250_000
    assert extract_amount("hola qué tal") is None


def test_build_recommendations_fact_vs_suggestion():
    from app.schemas.ui import RecommendationItem
    from app.services.agent.composer import build_recommendations
    summary = {"income": 22000, "expense": 15000, "net": 7000,
               "top_categories": [{"category": "Hogar", "amount": 6500, "pct": 43.3, "count": 8}]}
    categories = [{"category": "Hogar", "amount": 6500, "pct": 43.3, "count": 8},
                  {"category": "Restaurantes", "amount": 3200, "pct": 21.3, "count": 14}]
    budgets = [{"category": "Restaurantes", "spent": 3200, "limit": 3000, "pct": 106.7}]
    items = build_recommendations(summary, categories, budgets)
    assert len(items) >= 3
    assert all(isinstance(i, RecommendationItem) for i in items)
    assert any(i.kind == "suggestion" and "Presupuesto excedido" in i.title for i in items)
    assert all(i.basis for i in items)  # every item explains its source
