"""Contrato único del catálogo de herramientas MCP."""
import uuid

import pytest

from app.services.mcp_catalog import (
    CATALOG,
    DESTRUCTIVE_TOOLS,
    MCP_ALLOWED_TOOLS,
    TOOL_BY_NAME,
    WRITE_TOOLS,
    ToolValidationError,
    catalog_snapshot,
    get_contract,
    validate_arguments,
)


def test_catalog_has_exactly_the_twenty_tools():
    names = [contract.name for contract in CATALOG]
    assert len(names) == 20
    assert len(set(names)) == 20
    assert MCP_ALLOWED_TOOLS == frozenset(names)
    assert set(TOOL_BY_NAME) == MCP_ALLOWED_TOOLS
    assert WRITE_TOOLS == {
        "create_savings_goal", "update_savings_goal", "apply_savings_contribution",
    }
    assert DESTRUCTIVE_TOOLS == frozenset()


def test_every_contract_declares_risk_permissions_audit_and_output():
    for contract in CATALOG:
        assert contract.title
        assert contract.description
        assert contract.output_contract
        assert contract.permissions
        assert contract.audit_event.startswith("mcp_")
        assert contract.risk in ("read", "write", "sensitive", "destructive")
        if contract.is_write:
            assert contract.requires_confirmation is True
        else:
            assert contract.requires_confirmation is False


def test_every_input_schema_is_strict():
    for contract in CATALOG:
        schema = contract.input_schema()
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


def test_write_contracts_declare_confirmation_and_idempotency():
    assert get_contract("create_savings_goal").idempotency == "optional"
    assert get_contract("update_savings_goal").idempotency == "none"
    assert get_contract("apply_savings_contribution").idempotency == "required"
    assert get_contract("get_balance").idempotency == "none"
    assert get_contract("get_balance").sensitive_output is False
    assert get_contract("get_cards").sensitive_output is True


def test_validation_rejects_unknown_fields_and_invalid_values():
    with pytest.raises(ToolValidationError, match="unexpected"):
        validate_arguments("get_balance", {"unexpected": 1})
    with pytest.raises(ToolValidationError, match="tx_type"):
        validate_arguments("get_transactions", {"tx_type": "other"})
    with pytest.raises(ToolValidationError, match="month_a"):
        validate_arguments("compare_months", {"month_a": "2026-13", "month_b": "2026-10"})
    with pytest.raises(ToolValidationError, match="date_from"):
        validate_arguments("get_transactions", {"date_from": "2026-10-01"})
    with pytest.raises(ToolValidationError, match="goal_id"):
        validate_arguments("apply_savings_contribution", {"amount": 100})
    with pytest.raises(ToolValidationError, match="idempotency_key"):
        validate_arguments("apply_savings_contribution", {
            "goal_id": 1, "amount": 100, "idempotency_key": "no-es-uuid",
        })
    with pytest.raises(ToolValidationError, match="fecha límite"):
        validate_arguments("create_savings_goal", {
            "name": "Meta", "target_amount": 1_000, "deadline": "2000-01-01",
        })
    with pytest.raises(ToolValidationError, match="no permitido"):
        validate_arguments("create_savings_goal", {
            "name": "<script>alerta</script>", "target_amount": 1_000,
        })


def test_validation_accepts_valid_boundary_values():
    validated = validate_arguments("get_transactions", {
        "date_from": "2026-10-01", "date_to": "2026-10-31", "limit": 200,
    })
    assert validated.limit == 200
    validated = validate_arguments("apply_savings_contribution", {
        "goal_id": 1, "amount": 100, "idempotency_key": str(uuid.uuid4()),
    })
    assert validated.confirm is False


@pytest.mark.asyncio
async def test_direct_implementation_uses_the_same_validation(tmp_db):
    from tools.finance_tools import create_savings_goal_impl

    with pytest.raises(ToolValidationError, match="target_amount"):
        await create_savings_goal_impl("Meta inválida", 0)
    with pytest.raises(ToolValidationError, match="name"):
        await create_savings_goal_impl("x", 1_000)


def test_snapshot_is_serializable_and_matches_catalog():
    snapshot = catalog_snapshot()
    assert len(snapshot) == 20
    assert {item["name"] for item in snapshot} == MCP_ALLOWED_TOOLS
    assert all(item["input_schema"]["additionalProperties"] is False for item in snapshot)
