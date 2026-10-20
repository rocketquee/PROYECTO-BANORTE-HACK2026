# Banorte AI Finanzas — Prototipo

**Agente financiero con interfaces dinámicas generadas en tiempo real.**

> Prototipo educativo con **datos 100% sintéticos**. No está afiliado a Banorte,
> no solicita credenciales bancarias reales y **nunca mueve dinero real**.

---

## El problema que resuelve

Un chatbot financiero tradicional responde con un muro de texto: la misma pantalla
para cualquier intención y, para actuar, el usuario tiene que irse a otra app.

## La propuesta de valor

Aquí el agente **construye la pantalla que resuelve el problema**: interpreta la
intención, consulta datos con herramientas reales y renderiza componentes
interactivos (gráficos, tablas, simuladores, formularios) que permiten **actuar
dentro de la conversación**. Cada interacción con la UI regresa al agente y
produce nuevas acciones (ciclo cerrado).

**Flujo:** `Usuario → Agente IA → Herramientas → Datos financieros → Interfaz dinámica → Usuario`

## Arquitectura

```mermaid
flowchart LR
    U[Usuario] -->|solicitud| FE["Frontend Next.js (React + Recharts)"]
    FE -->|POST /api/agent/chat| BE["Backend FastAPI"]
    BE -->|"MCP stdio (list_tools / call_tool)"| MCP["Servidor MCP (FastMCP)"]
    MCP --> DB[("SQLite sintética")]
    BE -->|"contrato JSON validado (Pydantic)"| FE
    FE -->|"componentes React autorizados"| U
    U -->|"interacciones (confirmar, simular, filtrar)"| FE
```

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS + Recharts.
- **Backend**: FastAPI + Pydantic v2 + SQLite (datos sintéticos persistentes).
- **MCP**: SDK oficial de Python (`mcp`), transporte stdio, 18 herramientas.
- **IA**: proveedor configurable (OpenAI / Anthropic) o **modo demostración**
  sin API key (agente basado en reglas que usa las mismas herramientas MCP reales).

### El ciclo A2UI (interfaz que viaja)

1. El agente detecta la intención (LLM o reglas en modo demo).
2. Invoca herramientas MCP (`list_tools` → `call_tool`) sobre la base sintética.
3. Un **compositor determinista y auditado** genera el JSON de interfaz, validado
   con Pydantic (`extra="forbid"`): el modelo **nunca produce código ejecutable**.
4. El frontend mapea el JSON a componentes React autorizados (registro fijo).
5. Las interacciones (confirmar una meta, cambiar parámetros del simulador,
   clic en una categoría) regresan al backend/agente y generan nuevas respuestas.

## Estructura

```
banorte-ai-finanzas/
├── frontend/          # Next.js 15 + TS + Tailwind + Recharts
├── backend/           # FastAPI + Pydantic + SQLite
│   ├── app/           #   api/ core/ schemas/ services/agent/
│   └── tests/         #   pytest: cálculos, contrato UI, servicios, MCP, seguridad
├── mcp-server/        # Servidor MCP real (FastMCP, stdio)
├── docs/              # Arquitectura y decisiones técnicas
└── scripts/           # start-all.cmd / stop-all.cmd / run-tests.cmd
```

## Instalación (Windows, sin Anaconda)

Requisitos: **Python 3.11+** y **Node.js 18+**.

```cmd
:: 1. Entorno virtual + dependencias Python
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt -r mcp-server\requirements.txt

:: 2. Dependencias del frontend
cd frontend && npm install && cd ..
```

Opcional: copia `.env.example` a `.env` (raíz) y configura tu proveedor de IA.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `AI_PROVIDER` | `demo` (default, sin API key) · `openai` · `anthropic` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Para proveedor OpenAI |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Para proveedor Anthropic |
| `FRONTEND_ORIGIN` | CORS restrictivo (default `http://localhost:3000`) |
| `DEV_MODE` | `1` habilita `/docs`, `/openapi.json` y detalles técnicos. **Desactivado por defecto**; nunca se activa desde la interfaz pública. |

**No hay secretos en el frontend ni en el código.** Sin API key, la app corre en
modo demostración con el agente por reglas y las mismas herramientas MCP reales.

## Iniciar los servicios

**Un solo script:** `scripts\start-all.cmd` — levanta backend y frontend, espera a
que ambos estén listos, abre el navegador y avisa con un mensaje claro si falta
Python o Node. Para detener todo: `scripts\stop-all.cmd`.

Manual (2 terminales):

```cmd
:: Terminal 1 — Backend (solo localhost)
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

:: Terminal 2 — Frontend
cd frontend && npm run dev

:: El servidor MCP se lanza SOLO por el backend (transporte stdio).
:: Para probarlo aislado, ver mcp-server\README.md
```

## Herramientas MCP (18)

Consulta: `get_balance`, `get_transactions`, `get_cards`, `get_savings_goals`,
`analyze_spending`, `calculate_credit_simulation`, `get_monthly_summary`,
`get_budgets`, `get_spending_trend`, `compare_months`, `get_weekly_spending`,
`detect_recurring_charges`, `detect_anomalies`, `compare_credit_terms`,
`budget_vs_actual`, `project_savings`.

Escritura: `create_savings_goal`*, `update_savings_goal`*.

\* Escritura: devuelven `requires_confirmation` sin `confirm=True`; el backend
convierte eso en una acción pendiente que la UI confirma con el usuario. Además,
el backend **fuerza `confirm=False`** en cualquier llamada de escritura que venga
del LLM, de modo que el modelo nunca puede saltarse la confirmación humana.

## Pruebas

```cmd
.venv\Scripts\python -m pytest backend\tests -v
```

152 pruebas: matemática financiera, contrato de UI (rechaza tipos no autorizados
y props extra), servicios y persistencia, herramientas MCP (incluida una prueba
de integración real por protocolo stdio), y la suite de correcciones del reporte
QA: intención temporal (BUG-001), cero fugas de información (BUG-003), 40 ataques
de inyección (BUG-004), lenguaje coloquial (BUG-006), nuevas herramientas y
componentes (BUG-007), consistencia de datos (BUG-008), endurecimiento del
backend (BUG-009), formato mexicano (BUG-012), recomendaciones solo si se piden
(BUG-013), validaciones de escritura (BUG-014) e identidad (BUG-017).

## Seguridad y privacidad

- Solo datos sintéticos; sin credenciales bancarias, CVV ni números completos.
- SQL 100% parameterizado; CORS restringido al origen del frontend.
- Contrato UI con Pydantic `extra="forbid"`; el frontend solo renderiza tipos
  autorizados desde un registro fijo (nunca evalúa el JSON como código).
- Escrituras con confirmación explícita del usuario y rechazo de duplicados.
- **Sin fugas técnicas en la interfaz:** ni la UI ni las respuestas muestran
  nombres de herramientas, protocolos ni arquitectura (verificado con pruebas).
- **Guardas anti-manipulación:** 40 variantes de ataque probadas obtienen una
  negativa amable; el texto malicioso dentro de datos se neutraliza.
- `/docs` y `/openapi.json` deshabilitados salvo `DEV_MODE=1`; errores genéricos
  al usuario ("No pude hacer eso. ¿Lo intentamos de otra forma?") y detalle solo
  en el log; sin encabezados de versión del servidor; límite de 30 mensajes/10 s.
- El simulador de crédito es **educativo**: no es una oferta, tasa ni aprobación real.

## Accesibilidad (WCAG 2.2 AA)

- Letra base de 18 px con control A- / A / A+ persistente.
- Contraste ≥ 4.5:1 en texto y ≥ 3:1 en gráficos (paleta oscura verificada).
- Las rebanadas del pastel muestran nombre + porcentaje, con leyenda textual con
  valores; toda gráfica tiene resumen en palabras (`aria-label`) y vista "Ver
  como tabla".
- Botones de mínimo 44–48 px, foco visible, navegación por teclado.
- Respeta "reducir movimiento" del sistema.
- Glosario "¿Qué significa?" (CAT, plazo, tasa, pago mínimo) en el simulador.

## Guion de demostración (3–5 min)

1. Abre `http://localhost:3000` → dashboard con KPIs, gráficas, metas.
2. En **Asistente IA**: *"¿Cómo han cambiado mis gastos en los últimos 4 meses?"*
   → gráfica de líneas de 4 meses con valores y conclusión (sin pastel ni
   recomendaciones no pedidas).
3. *"Analiza mis gastos de este mes"* → pastel con etiquetas y valores; alterna
   "Ver como tabla". "ahora en barras" cambia el tipo.
4. *"Ayúdame a ahorrar $5,000"* → formulario + confirmación con resumen; al
   confirmar se persiste y aparece en Ahorro y metas.
5. *"¿Cuánto podría pagar mensualmente por un crédito?"* → simulador vivo con
   glosario "¿Qué significa?" y aviso de que no es oferta.
6. *"¿Qué cargos fijos tengo?"* / *"¿tengo cargos duplicados?"* → listas de
   cargos recurrentes y alertas.
7. La conversación sobrevive a cambiar de pantalla y a recargar (historial en la
   barra lateral, con nueva conversación y borrado con confirmación).

## Mejoras futuras

- Autenticación real (OAuth) y multiusuario.
- Streaming de respuestas del agente (SSE).
- Aprobaciones de escritura persistentes (tabla `pending_actions`).
- Resumen semanal proactivo y alertas de gasto por categoría.
- CAT y comisiones en el simulador; perfilamiento de inversión.

## Problemas conocidos y limitaciones (modo demostración)

- La comprensión del lenguaje natural es por **reglas**: cubre los casos probados
  (ortografía común, coloquialismos, cantidades en palabras, fechas relativas),
  pero frases muy libres pueden requerir `AI_PROVIDER=anthropic|openai`.
- Los datos son ficticios por diseño; el prototipo **no** se conecta a bancos.
- Los pagos, transferencias, contactos, inversiones y seguros son secciones
  simuladas informativas (no mueven dinero ni guardan instrumentos reales).
- El límite de peticiones (30/10 s) es en memoria: se reinicia al reiniciar el
  backend; para producción usar Redis o similar.
- Las conversaciones se guardan en `localStorage` del navegador (por equipo y
  navegador); no hay sincronización multi-dispositivo ni servidor de historial.
