# Servidor MCP — Banorte AI Finanzas

Servidor MCP real (SDK oficial de Python `mcp`, transporte **stdio**) que expone
las herramientas financieras del prototipo sobre la base de datos SQLite sintética.

## Herramientas disponibles

| Herramienta | Tipo | Descripción |
|---|---|---|
| `get_balance` | lectura | Saldo total y cuentas de demostración |
| `get_transactions` | lectura | Movimientos con filtros (fechas, categoría, texto) |
| `get_cards` | lectura | Tarjetas ficticias (solo últimos 4 dígitos) |
| `get_savings_goals` | lectura | Metas de ahorro y progreso |
| `analyze_spending` | lectura | Gastos por categoría y periodo |
| `calculate_credit_simulation` | cálculo | Simulación de crédito (francés/alemán) |
| `get_monthly_summary` | lectura | Resumen mensual (ingresos, gastos, balance) |
| `get_budgets` | lectura | Presupuesto: gasto vs límites por categoría |
| `create_savings_goal` | **escritura** | Crear meta; requiere `confirm=True` |
| `update_savings_goal` | **escritura** | Actualizar meta; requiere `confirm=True` |
| `apply_savings_contribution` | **escritura** | Abonar a una meta; valida saldo/restante, registra movimiento y requiere confirmación + clave idempotente |

Las herramientas de escritura devuelven `{"status": "requires_confirmation", ...}`
si no se pasa `confirm=True`. El backend convierte eso en una acción pendiente que
la UI muestra al usuario para confirmar. Nunca se mueve dinero real.

## Ejecución

Con el venv del proyecto (donde instalaste `mcp`):

```cmd
.venv\Scripts\python mcp-server\server.py
```

El proceso se queda leyendo JSON-RPC por stdio — eso es correcto; está diseñado
para ser lanzado por un cliente MCP.

## Cómo se conecta el backend (agente)

El backend FastAPI lo lanza automáticamente al arrancar
(`app/services/mcp_client.py`, transporte stdio con `sys.executable`), hace
`initialize` + `list_tools` (descubrimiento real de herramientas) y expone
`call_tool` al agente. Si el servidor MCP no arranca, el chat responde 503 con
un mensaje claro.

## Configuración para otros clientes (p. ej. Claude Desktop)

```json
{
  "mcpServers": {
    "banorte-finance": {
      "command": "C:\\ruta\\al\\proyecto\\.venv\\Scripts\\python.exe",
      "args": ["C:\\ruta\\al\\proyecto\\mcp-server\\server.py"]
    }
  }
}
```

## Nota de arquitectura (trade-off documentado)

`mcp-server/tools/finance_tools.py` importa la capa de servicios del backend
(`backend/app/services`) agregando esa carpeta a `sys.path`. Para un prototipo
esto evita duplicar la lógica de datos; en producción convendría extraer esa
capa a un paquete compartido instalable.
