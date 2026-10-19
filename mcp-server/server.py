"""Banorte AI Finanzas — MCP server (official `mcp` Python SDK, FastMCP, stdio).

Run standalone (any MCP client):
    python mcp-server/server.py

Tools are discovered and invoked over the Model Context Protocol. Data comes
from the shared synthetic SQLite database; write tools require confirm=True.
"""
from mcp.server.fastmcp import FastMCP

from tools.finance_tools import (
    analyze_spending_impl,
    calculate_credit_simulation_impl,
    create_savings_goal_impl,
    get_balance_impl,
    get_budgets_impl,
    get_cards_impl,
    get_monthly_summary_impl,
    get_savings_goals_impl,
    get_transactions_impl,
    update_savings_goal_impl,
)

mcp = FastMCP(
    "banorte-finance",
    instructions=(
        "Herramientas financieras del prototipo 'Banorte AI Finanzas' (datos sintéticos). "
        "Consulta saldos, movimientos, tarjetas, metas, gastos y resúmenes; simula créditos. "
        "Las herramientas de escritura (metas de ahorro) requieren confirmación explícita del "
        "usuario (confirm=True) y NUNCA mueven dinero real."
    ),
)

mcp.tool(name="get_balance", description="Consulta el saldo total y las cuentas de demostración.")(get_balance_impl)
mcp.tool(name="get_transactions", description="Consulta movimientos con filtros opcionales: date_from, date_to (YYYY-MM-DD), "
                     "category, tx_type ('income'|'expense'), q (texto), limit.")(get_transactions_impl)
mcp.tool(name="get_cards", description="Consulta tarjetas de demostración (solo datos no sensibles, últimos 4 dígitos).")(get_cards_impl)
mcp.tool(name="get_savings_goals", description="Obtiene las metas de ahorro y su progreso.")(get_savings_goals_impl)
mcp.tool(name="create_savings_goal", description="Crea una meta de ahorro. Requiere confirm=True (confirmación del usuario) "
                     "para escribir; sin él devuelve 'requires_confirmation'.")(create_savings_goal_impl)
mcp.tool(name="update_savings_goal", description="Actualiza una meta de ahorro existente. Requiere confirm=True.")(update_savings_goal_impl)
mcp.tool(name="analyze_spending", description="Analiza gastos por categoría en un periodo (year+month o date_from+date_to).")(analyze_spending_impl)
mcp.tool(name="calculate_credit_simulation", description="Calcula la simulación de un crédito (método 'frances' o 'aleman'). "
                     "Simulación educativa; no es una oferta real.")(calculate_credit_simulation_impl)
mcp.tool(name="get_monthly_summary", description="Resumen financiero del mes: ingresos, gastos, balance y top categorías.")(get_monthly_summary_impl)
mcp.tool(name="get_budgets", description="Presupuesto del mes: gasto por categoría contra límites configurados.")(get_budgets_impl)

if __name__ == "__main__":
    mcp.run(transport="stdio")
