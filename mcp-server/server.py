"""Banorte AI Finanzas — MCP server (official `mcp` Python SDK, FastMCP, stdio).

Run standalone (any MCP client):
    python mcp-server/server.py

Tools are discovered and invoked over the Model Context Protocol. Data comes
from the shared synthetic SQLite database; write tools require confirm=True.
"""
from mcp.server.fastmcp import FastMCP

from tools.finance_tools import (
    analyze_spending_impl,
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
mcp.tool(name="get_spending_trend", description="Tendencia de gastos de los últimos N meses (opcional por categoría).")(get_spending_trend_impl)
mcp.tool(name="compare_months", description="Compara dos meses (YYYY-MM): ingresos, gastos y balance.")(compare_months_impl)
mcp.tool(name="get_weekly_spending", description="Gasto total por semana de las últimas N semanas.")(get_weekly_spending_impl)
mcp.tool(name="detect_recurring_charges", description="Detecta cargos fijos o recurrentes (suscripciones, pagos mensuales).")(detect_recurring_charges_impl)
mcp.tool(name="detect_duplicates", description="Detecta cobros duplicados (mismo cargo aplicado dos veces el mismo día).")(detect_duplicates_impl)
mcp.tool(name="detect_anomalies", description="Detecta cargos inusualmente altos para su categoría, excluyendo recurrentes y duplicados.")(detect_anomalies_impl)
mcp.tool(name="project_savings", description="Proyecta cuántos meses necesitas para una meta si ahorras X al mes.")(project_savings_impl)
mcp.tool(name="compare_credit_terms", description="Compara plazos de crédito (12/24/36 meses) para un monto dado.")(compare_credit_terms_impl)
mcp.tool(name="budget_vs_actual", description="Presupuesto planeado contra gasto real, con categorías excedidas.")(budget_vs_actual_impl)

if __name__ == "__main__":
    mcp.run(transport="stdio")
