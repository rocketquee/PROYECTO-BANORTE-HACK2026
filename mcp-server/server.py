"""Banorte AI Finanzas — MCP server (official `mcp` Python SDK, FastMCP, stdio).

Run standalone (any MCP client):
    python mcp-server/server.py

Tools are discovered and invoked over the Model Context Protocol. Data comes
from the shared synthetic SQLite database; write tools require confirm=True.

The catalog in `app.services.mcp_catalog` is the single source of truth for
tool names, descriptions, input schemas, risk, permissions, confirmations,
idempotency and output contracts. This server only wires implementations to
that catalog.
"""
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from tools.finance_tools import (
    analyze_spending_impl,
    apply_savings_contribution_impl,
    budget_vs_actual_impl,
    calculate_credit_simulation_impl,
    compare_credit_terms_impl,
    compare_months_impl,
    create_savings_goal_impl,
    detect_anomalies_impl,
    detect_duplicates_impl,
    detect_recurring_charges_impl,
    get_balance_impl,
    get_budgets_impl,
    get_cards_impl,
    get_monthly_summary_impl,
    get_savings_goals_impl,
    get_spending_trend_impl,
    get_transactions_impl,
    get_weekly_spending_impl,
    project_savings_impl,
    set_budget_limit_impl,
    update_savings_goal_impl,
)
from app.services.mcp_catalog import (  # noqa: E402
    CATALOG,
    TOOL_BY_NAME,
    ToolContract,
    ToolValidationError,
    get_contract,
    validate_arguments,
)

TOOL_IMPLS = {
    "get_balance": get_balance_impl,
    "get_transactions": get_transactions_impl,
    "get_cards": get_cards_impl,
    "get_savings_goals": get_savings_goals_impl,
    "create_savings_goal": create_savings_goal_impl,
    "update_savings_goal": update_savings_goal_impl,
    "apply_savings_contribution": apply_savings_contribution_impl,
    "set_budget_limit": set_budget_limit_impl,
    "analyze_spending": analyze_spending_impl,
    "calculate_credit_simulation": calculate_credit_simulation_impl,
    "get_monthly_summary": get_monthly_summary_impl,
    "get_budgets": get_budgets_impl,
    "get_spending_trend": get_spending_trend_impl,
    "compare_months": compare_months_impl,
    "get_weekly_spending": get_weekly_spending_impl,
    "detect_recurring_charges": detect_recurring_charges_impl,
    "detect_duplicates": detect_duplicates_impl,
    "detect_anomalies": detect_anomalies_impl,
    "project_savings": project_savings_impl,
    "compare_credit_terms": compare_credit_terms_impl,
    "budget_vs_actual": budget_vs_actual_impl,
}


class CatalogFastMCP(FastMCP):
    """FastMCP that validates raw protocol arguments against the catalog."""

    async def call_tool(self, name: str, arguments: dict[str, Any] | None):
        if get_contract(name) is None:
            return await super().call_tool(name, arguments or {})
        try:
            validated = validate_arguments(name, arguments)
        except ToolValidationError as exc:
            raise ToolError(str(exc)) from exc
        return await super().call_tool(name, validated.model_dump_one_level())


mcp = CatalogFastMCP(
    "banorte-finance",
    instructions=(
        "Herramientas financieras del prototipo 'Banorte AI Finanzas' (datos sintéticos). "
        "Consulta saldos, movimientos, tarjetas, metas, gastos y resúmenes; simula créditos. "
        "Las herramientas de escritura (metas de ahorro) requieren confirmación explícita del "
        "usuario (confirm=True) y NUNCA mueven dinero real."
    ),
)


def _annotations(contract: ToolContract) -> ToolAnnotations:
    return ToolAnnotations(
        title=contract.title,
        readOnlyHint=contract.risk == "read",
        destructiveHint=contract.risk == "destructive",
        idempotentHint=(
            contract.risk == "read"
            or contract.idempotency == "required"
            or contract.name == "update_savings_goal"
        ),
        openWorldHint=False,
    )


def _register_tools() -> None:
    if set(TOOL_IMPLS) != set(TOOL_BY_NAME):
        missing = sorted(set(TOOL_BY_NAME) - set(TOOL_IMPLS))
        extra = sorted(set(TOOL_IMPLS) - set(TOOL_BY_NAME))
        raise RuntimeError(
            f"Catálogo e implementaciones MCP no coinciden; faltan={missing}, sobran={extra}."
        )
    for contract in CATALOG:
        mcp.add_tool(
            TOOL_IMPLS[contract.name],
            name=contract.name,
            title=contract.title,
            description=contract.description,
            annotations=_annotations(contract),
            meta={
                "risk": contract.risk,
                "permissions": list(contract.permissions),
                "requires_confirmation": contract.requires_confirmation,
                "idempotency": contract.idempotency,
                "sensitive_output": contract.sensitive_output,
            },
        )
        registered = mcp._tool_manager.get_tool(contract.name)
        registered.parameters = contract.input_schema()


_register_tools()


if __name__ == "__main__":
    mcp.run(transport="stdio")
