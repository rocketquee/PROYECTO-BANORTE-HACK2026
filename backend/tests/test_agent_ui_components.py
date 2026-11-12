"""Generación real de los cuatro componentes nuevos del catálogo A2UI.

Cada mensaje de `ui_catalog.COMPONENT_EXAMPLES` recorre el motor demo con las
herramientas MCP reales sobre una base temporal. No se simulan cifras: el plan
se construye con los mismos resultados que devuelve el dominio.
"""
import asyncio

import pytest

import tools.finance_tools as ft
from app.schemas.api import ChatRequest
from app.services.agent import composer, loop, orchestrator as orch, ui_catalog

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_monthly_summary": ft.get_monthly_summary_impl,
    "get_savings_goals": ft.get_savings_goals_impl,
    "analyze_spending": ft.analyze_spending_impl,
    "get_spending_trend": ft.get_spending_trend_impl,
    "get_budgets": ft.get_budgets_impl,
    "calculate_credit_simulation": ft.calculate_credit_simulation_impl,
}


async def fake_call(name: str, arguments: dict) -> dict:
    return await IMPLS[name](**arguments)


@pytest.fixture(autouse=True)
def patched_agent(tmp_db, monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch, "get_provider", lambda: None)
    monkeypatch.setattr(loop, "get_provider", lambda: None)
    orch.session_store.clear()
    yield
    orch.session_store.clear()


def _demo_plan(message: str, session_id: str) -> dict:
    response = asyncio.run(orch.handle_chat(ChatRequest(
        message=message, session_id=session_id,
    )))
    plan = loop.attach_ui_plan(response).ui_plan
    assert plan is not None, message
    return plan


def _component(plan: dict, kind: str) -> dict:
    return next(
        component for component in plan["components"] if component["type"] == kind
    )


@pytest.mark.parametrize(
    ("kind", "session_id"),
    [
        ("PlanDePago", "example-plan-de-pago"),
        ("LineChart", "example-line-chart"),
        ("Slider", "example-slider"),
        ("BudgetAllocator", "example-budget-allocator"),
    ],
)
def test_component_example_generates_the_declared_component(kind, session_id):
    plan = _demo_plan(ui_catalog.COMPONENT_EXAMPLES[kind], session_id)
    assert kind in {component["type"] for component in plan["components"]}


def test_plan_de_pago_copies_domain_payment_and_cat():
    from app.services import credit

    plan = _demo_plan(
        ui_catalog.COMPONENT_EXAMPLES["PlanDePago"], "example-plan-values",
    )
    component = _component(plan, "PlanDePago")
    term = component["terms"][0]

    assert component["amount"] == 100_000
    assert component["annual_rate"] == 15.9
    assert term["months"] == 24
    assert term["cat_pct"] == credit.cat_estimate(15.9)
    assert term["monthly_payment"] > 0


def _slider_action(component: dict, value: float) -> str:
    """Mismo mensaje que `sliderAction()` de frontend/src/lib/uiPlan.mjs.

    El cliente formatea MXN con `Intl.NumberFormat("es-MX")` (dos decimales) y
    los meses como entero. Se reproduce aquí para que el E2E use el texto exacto
    que produce la interfaz, no una variante equivalente.
    """
    if component["unit"] == "MXN":
        display = composer.money2(value)
    else:
        display = f"{value:g}"
    return component["recalculate_message"].replace("{value}", display)


def test_slider_action_recalculates_through_the_agent_and_returns_a_new_plan():
    prepared = _demo_plan(
        ui_catalog.COMPONENT_EXAMPLES["Slider"], "example-slider-recalc",
    )
    amount_slider = next(
        component for component in prepared["components"]
        if component["type"] == "Slider" and component["param"] == "amount"
    )
    months_slider = next(
        component for component in prepared["components"]
        if component["type"] == "Slider" and component["param"] == "months"
    )

    amount_message = _slider_action(amount_slider, 150_000)
    assert amount_message == (
        "Recalcula el crédito con un monto de $150,000.00 a 24 meses "
        "al 15.9% anual."
    )
    recalculated = _demo_plan(amount_message, "example-slider-recalc")
    amount_plan = _component(recalculated, "PlanDePago")
    assert amount_plan["amount"] == 150_000
    assert amount_plan["terms"][0]["months"] == 24

    months_message = _slider_action(months_slider, 36)
    assert months_message == (
        "Recalcula el crédito de $100,000 a un plazo de 36 meses "
        "al 15.9% anual."
    )
    recalculated = _demo_plan(months_message, "example-slider-recalc")
    months_plan = _component(recalculated, "PlanDePago")
    assert months_plan["amount"] == 100_000
    assert months_plan["terms"][0]["months"] == 36


def test_line_chart_uses_the_spending_trend_series():
    plan = _demo_plan(
        ui_catalog.COMPONENT_EXAMPLES["LineChart"], "example-line-values",
    )
    component = _component(plan, "LineChart")

    assert len(component["points"]) >= 2
    assert component["unit"] == "MXN"
    assert all(point["value"] >= 0 for point in component["points"])
    assert component["period"]


def test_budget_allocator_amounts_sum_income_and_keep_50_30_20():
    plan = _demo_plan(
        ui_catalog.COMPONENT_EXAMPLES["BudgetAllocator"], "example-budget-values",
    )
    component = _component(plan, "BudgetAllocator")

    assert {item["bucket"]: item["pct"] for item in component["buckets"]} == {
        "necesidades": 50.0, "deseos": 30.0, "ahorro": 20.0,
    }
    assert sum(item["amount"] for item in component["buckets"]) == pytest.approx(
        component["income"], abs=0.01,
    )
