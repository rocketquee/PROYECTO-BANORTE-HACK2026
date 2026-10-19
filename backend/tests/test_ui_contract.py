"""The dynamic-UI contract: only authorized components, strict props,
no executable code can slip through."""
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.ui import ChatResponse, UISpec

UISpecAdapter = TypeAdapter(UISpec)


def _valid_spending_chart() -> dict:
    return {
        "type": "spending_chart",
        "title": "Gastos por categoría",
        "period": "Octubre 2026",
        "series": [{"category": "Supermercado", "amount": 4200.0, "pct": 35.5, "count": 12}],
    }


def test_valid_spec_passes():
    spec = UISpecAdapter.validate_python(_valid_spending_chart())
    assert spec.type == "spending_chart"


def test_unknown_component_type_rejected():
    with pytest.raises(ValidationError):
        UISpecAdapter.validate_python({"type": "iframe", "src": "https://evil.example"})


def test_extra_props_rejected_blocks_injection():
    bad = _valid_spending_chart() | {"onClick": "alert(1)"}
    with pytest.raises(ValidationError):
        UISpecAdapter.validate_python(bad)


def test_credit_simulator_requires_all_fields():
    with pytest.raises(ValidationError):
        UISpecAdapter.validate_python({"type": "credit_simulator", "title": "x"})


def test_chat_response_round_trip_with_multiple_components():
    resp = ChatResponse.model_validate({
        "message": "Aquí tienes",
        "mode": "demo",
        "ui": [
            _valid_spending_chart(),
            {"type": "recommendation_list", "title": "Recomendaciones",
             "items": [{"title": "Reduce Restaurantes", "detail": "-15%",
                        "kind": "suggestion", "basis": "Datos calculados"}]},
        ],
        "tools_used": ["analyze_spending"],
    })
    assert [u.type for u in resp.ui] == ["spending_chart", "recommendation_list"]
    # serializes cleanly for the frontend
    payload = resp.model_dump()
    assert payload["ui"][0]["type"] == "spending_chart"


def test_pending_action_shape():
    resp = ChatResponse.model_validate({
        "message": "Confirma",
        "mode": "demo",
        "pending_action": {"id": "pa_123", "action": "create_savings_goal",
                           "params": {"name": "Ahorro", "target_amount": 5000},
                           "description": "Crear meta"},
    })
    assert resp.pending_action.action == "create_savings_goal"
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({
            "message": "x", "mode": "demo",
            "pending_action": {"id": "pa", "action": "delete_account", "params": {},
                               "description": "no permitida"},
        })
