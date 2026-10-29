# Informe de auditoría — Fase 1
### Proyecto: `proyecto-banorte-ai-finanzas` (prototipo educativo, datos sintéticos, SQLite)
### Rol: ingeniero de software senior / responsable de integridad de datos
### Fecha: 2026-10-22 · Alcance: auditoría de causas raíz (Clases A–E) · **Sin cambios de código aplicados todavía**

---

## 0. Método y alcance

**Qué se auditó** (lectura completa o por bloques, no muestreo):

| Artefacto | Rol en el sistema |
|---|---|
| `backend/app/services/finance.py` | Única capa de métricas derivadas (invariantes INV-1…INV-4, INV-9) |
| `backend/app/core/seed.py` | Esquema físico de la base y datos sembrados |
| `backend/app/core/database.py` | Transacciones, PRAGMAs, inicialización |
| `backend/app/core/config.py` | Configuración, `DEV_MODE`, ruta de la base |
| `backend/app/core/structured_logging.py` | Registro estructurado con `trace_id` |
| `backend/app/api/routes.py` | Superficie REST (validación duplicada, confirmaciones) |
| `backend/app/services/agent/orchestrator.py` | Interpretación de intención, validación de entradas, formato (Clases B–E) |
| `backend/app/services/agent/composer.py` | Composición determinista de UI (bases de porcentajes, INV-7) |
| `mcp-server/tools/finance_tools.py` | Operaciones de escritura (causa raíz de Clase A) |
| `frontend/src/components/dynamic/BudgetPlanner.tsx`, `.../SectionView.tsx` | Recálculo de métricas en el cliente (INV-9) |
| `backend/tests/*` | Contratos y expectativas actualmente codificadas |

**Evidencia en la base real** (`backend/data/banorte.db`, 967 movimientos) — ejecutada en modo solo lectura:

```
SCHEMA transactions → type TEXT NOT NULL CHECK (type IN ('income','expense'))   ← no existe 'transfer'
Categorías (count, suma): ... ('Ahorro', 1, 22500.0) ...                        ← categoría de gasto falsa
COUNT por tipo: expense=942, income=25                                          ← ninguna transferencia
accounts: Nómina 24,580.35 · Ahorro 35,700.00 · Digital 3,140.80 = 63,421.15
savings_goals: Fondo de emergencia 18,500 · Viaje a Japón 8,200 · Compra planeada 22,500 = 49,200
```

**Conclusión de la evidencia anterior:** la base **ya está inconsistente**. La meta «Compra planeada» (objetivo 45,000) tiene 22,500 ahorrados; la cuenta de ahorro bajó de 58,200.00 a 35,700.00 (−22,500) **y además** existe un movimiento `type='expense', category='Ahorro'` por 22,500.00. Un único abono a meta produjo **dos efectos contables simultáneos** (débito de cuenta + gasto), es decir, doble conteo de un mismo movimiento de dinero propio.

---

## 1. Resumen ejecutivo

El defecto raíz es de **modelo de dominio, no de cálculo**: el sistema **no tiene el concepto de "transferencia"**. El esquema físico solo admite `income` y `expense` ([seed.py#L34](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/core/seed.py#L34)), y la única operación que mueve dinero entre cuentas propias (abono a meta) lo registra como **gasto** ([finance_tools.py#L380-L385](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L380-L385)). A partir de ahí, **todas** las métricas derivadas heredan el error porque todas filtran por `type='expense'` para decidir qué es "gasto".

Además, el saldo no se deriva del libro de movimientos: los saldos de cuentas son **fixtures estáticos** que ninguna escritura (salvo el abono a meta) modifica; por ello INV-2 e INV-3 son hoy **no verificables por reconciliación**.

Ocho familias de fallo se repiten por todo el sistema (Clases A–E), todas con la misma forma: **una regla de dominio vive dispersa en varias capas** (validación en la API y otra distinta en el MCP; métricas en `finance.py` y otras recalculadas en el frontend; interpretación de intención mezclada con alertas de seguridad).

---

## 2. Clase A — Integridad contable (crítica)

> Síntoma reportado: escribir en metas altera gastos, categorías, balance del mes y saldo, y el sistema llega a conclusiones falsas.

### A-1 · Causa raíz: una transferencia se registra como gasto
[finance_tools.py#L380-L385](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L380-L385)

```
INSERT INTO transactions (date, description, amount, type, category, account_id)
VALUES (?,?,?,?,?,?)   → ("Abono a meta: X", 22500.0, "expense", "Ahorro", <cuenta>)
```
El abono debita cuentas (correcto bajo INV-3) **y** se inserta como `expense` (viola INV-1). Un movimiento entre cuentas propias se trata como consumo.

### A-2 · El modelo físico no puede representar la regla
[seed.py#L34](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/core/seed.py#L34) — `CHECK (type IN ('income','expense'))`. El tercer tipo (`transferencia`) que exige el modelo **está prohibido por la propia base**. Cualquier corrección sin migrar el esquema queda bloqueada por la restricción.

### A-3 · `total_balance` no incluye el ahorro en metas (viola INV-2)
[finance.py#L23-L24](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L23-L24) — `SUM(balance) FROM accounts`.
Evidencia real: la app reporta **63,421.15**; conforme a INV-2 el total debería ser **112,621.15** (63,421.15 + 49,200). El "Saldo total" mostrado en Inicio, Dashboard y respuestas del asistente está subestimado en 49,200.

### A-4 · `available_balance` conflaciona "disponible" con "total" (viola INV-3)
[finance_tools.py#L390](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L390) — devuelve `finance.total_balance(conn)` **después** del débito y lo etiqueta `available_balance`. Hoy coincide por accidente (porque A-3 hace que "total" = solo cuentas); en cuanto se corrija A-3, este campo pasará a **incluir el ahorro en metas** y a ser incorrecto. Disponible debe ser *saldo en cuentas*.

### A-5 · El "Balance del mes" cuenta el abono como gasto
[finance.py#L93-L116](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L93-L116) — `expense` suma `type='expense'` y `net = income - expense`. El abono infla gastos y **falsea el balance del mes**, que es la cifra sobre la que el asistente concluye ("tu balance del mes es…").

### A-6 · Aparece una categoría de gasto falsa ("Ahorro")
[finance.py#L74-L90](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L74-L90) (`WHERE type='expense' GROUP BY category`) y su propagación a:
- [finance.py#L115](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L115) `top_categories`,
- [finance.py#L367-L394](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L367-L394) `budget_overview` (`total_spent`, `available`),
- [finance.py#L399-L413](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L399-L413) `dashboard.categories`.

Evidencia: `('Ahorro', 1, 22500.0)` en la base real. La persona ve 22,500 de "gastos" que no gastó.

### A-7 · Anomalías, cobros fijos, duplicados y tendencias también asumen `expense = gasto`
[finance.py#L213](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L213) (`recurring_charges`), [#L242](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L242) (`detect_duplicates`), [#L263](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L263) (`detect_anomalies`), [#L152](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L152) y [#L158](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L158) (`spending_trend`), [#L180](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L180) (`weekly_spending`). Cualquier movimiento mal tipado entra como "gasto", "anomalía" o "cobro repetido", violando INV-1 ("una transferencia no modifica anomalías ni pagos fijos").

### A-8 · `saved_amount` sin límites y auto-completado (viola INV-4)
[finance.py#L319-L348](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L319-L348): `saved_amount` y `add_amount` se aceptan sin rango; `add_amount` puede ser negativo; `saved_amount >= target_amount` auto-marca `"completada"` sin validar. **Tres caminos lo alcanzan sin bajar por el MCP:**
- MCP [finance_tools.py#L247-L265](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L247-L265) (`update_savings_goal_impl`, sin validación ni idempotencia),
- REST [routes.py#L135-L144](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L135-L144) (`PATCH /goals/{id}`),
- REST [routes.py#L123-L132](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L123-L132) (`POST /goals`).

### A-9 · El saldo no se deriva del libro (viola INV-2/INV-3/INV-9)
[seed.py#L63-L67](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/core/seed.py#L63-L67) fija los saldos como constantes y **ninguna** ruta de escritura los actualiza a partir de los movimientos (nómina, gastos). Resultado: el libro tiene 281,370.67 de ingresos en 12 meses pero los saldos no reflejan flujo alguno. Es la razón por la que hoy **no existe reconciliación posible**: no hay una identidad contable que relacionar.

### A-10 · El frontend no conoce tipos distintos de ingreso/gasto
[SectionView.tsx#L123](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/frontend/src/components/SectionView.tsx#L123) firma con `t.type === "income" ? "+" : "−"`: un futuro movimiento `transferencia` se pintaría como decremento negativo.

### A-11 · Confirmaciones fuera del modelo INV-5
[orchestrator.py#L2277-L2286](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L2277-L2286): `execute_pending(action_id)` confirma a partir de un `action_id` provisto por el cliente y guardado en un diccionario **global de proceso** (`_PENDING`), sin token de evento verificado en servidor. La ruta de abonos sí usa `confirmation_token`, pero la de creación/edición de metas no. Además, la idempotencia de `create_savings_goal` es **opcional** ([finance_tools.py#L206](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L206)) y `update_savings_goal` **no la tiene**.

---

## 3. Clase B — Prioridad de interpretación

El principio exigido es **(1) entidades conocidas → (2) intención → (3) alertas**, y las alertas deben exigir señales explícitas y de alta precisión. El orden real es el inverso.

### B-1 · Orden invertido: alertas antes que entidades
[orchestrator.py#L423-L461](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L423-L461): `detect_intent` evalúa en este orden `sensitive` (L426) → `_INJECTION_PATTERNS`/refusal (L428) → fraud (L430) → emergency (L433) → antifraud (L435) → transfer (L438) → … → `out_of_scope` (L460) y solo al final resuelve intención de dominio. **No existe ninguna fase de resolución de entidades por coincidencia aproximada** antes de las alertas.

### B-2 · Una palabra aislada dispara alerta de seguridad
[_SENSITIVE_LABEL](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L113-L117) incluye `clave`, `token`, `nip`, `cvv`, `contraseña`. Una consulta legítima que contenga el **nombre de una meta o categoría** con esas palabras ("¿cuánto llevo en *Clave de seguridad*?", "abona a mi meta *Token*") se clasifica `sensitive` y pierde contra `SENSITIVE_MESSAGE`, antes de mirar las entidades existentes.

### B-3 · Patrones de inyección con colisiones de lenguaje normal
[_INJECTION_PATTERNS](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L374-L394): `\btools?\b` (L383) y `\bconfig\b` (L388) → `refusal`. Una meta llamada "Config" o una pregunta coloquial que use "tools" produce el rechazo genérico.

### B-4 · `out_of_scope` con falsos positivos coloquiales
[_OUT_OF_SCOPE_PATTERNS](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L396-L402): `bolsa`, `acciones`, `cripto`, `partido`, `receta`, `película`. Consultas financieras legítimas como "gastos de la *receta* médica" o "¿me alcanza para el *partido* del domingo?" caen en `out_of_scope` **antes** de intentar resolver la categoría real.

### B-5 · El nombre de un objeto nuevo se infiere del texto de la pregunta (prohibido)
[_demo_savings#L1078-L1103](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1078-L1103): con el regex de L1083-L1088 se deriva el nombre de la meta nueva desde la frase ("ayúdame a ahorrar 5,000 *para ir a Cancún*" → meta "Ir a cancun"). El requisito es que **solo** se cree con nombre declarado explícitamente o confirmado en formulario, nunca inferido de una pregunta.

### B-6 · Alertas de seguridad exigen precisión, no una palabra
Las reglas de fraude/emergencia/antifraude ([L430-L437](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L430-L437)) se evalúan antes que cualquier intención financiera; p. ej. "¿tengo cargos *sospechosos*?" coexiste con `anomalies` (L491) y gana `antifraud`/`fraud` según co-ocurrencia, sin priorizar la entidad o la intención declarada.

---

## 4. Clase C — Consultas que no se resuelven

**Causa común:** la intención se resuelve por regex de frases sobre el texto completo, sin una fase de resolución de entidades (metas, categorías) que falte. Cuando ninguna frase casa, se cae a `unknown` y se responde `UNKNOWN_MESSAGE` ([L2315-L2318](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L2315-L2318)).

Casos derivados del código (no de textos de pruebas), con la razón exacta:

| Consulta legítima | Resultado actual | Causa |
|---|---|---|
| «¿cuánto llevo ahorrado en Viaje a Japón?» | «No entendí» | el patrón de ahorro es `ahorro`/`ahorrar` ([L503-L505](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L503-L505)); "ahorrado" no casa y no hay resolución de la meta |
| «¿cuánto me falta para Viaje a Japón?» | «No entendí» | no existe patrón de "cuánto falta" por meta; ninguna entidad se consulta |
| «¿en qué puedo recortar?» | «No entendí» | `advice` exige `cómo puedo (reducir\|ahorrar\|mejorar)` ([L499-L501](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L499-L501)); "recortar" no casa |
| «compara comida y transporte este mes» | cae a `spending` genérico | `compare` exige `\bmes\b` o meses explícitos + `compar` ([L482-L484](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L482-L484)); la comparación entre categorías no existe |
| «proyecta mi meta Viaje a Japón si ahorro 2,000 al mes» | depende de dos números sueltos | `projection` no acepta el nombre de la meta; la meta real se ignora |
| «¿cuánto he gastado este año en Educación?» | responde al mes actual | no hay intención de periodo anual; `resolve_months_count` solo aplica a `trend` |

Impacto: **la mayoría de las capacidades existen solo para el mes en curso, sin parámetro de entidad**, y no hay tolerancia a errores de escritura ni a lenguaje coloquial fuera de un puñado de sinónimos ([CATEGORY_SYNONYMS](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L204-L218)). Las capacidades exigidas (cuánto falta, cuánto llevo, proyección por meta, aportación parcial, recortes, comparación entre periodos y entre categorías) **no están cubiertas de forma uniforme para todas las metas y categorías**.

---

## 5. Clase D — Validación

### D-1 · Montos pequeños válidos se descartan
[extract_amount#L278-L292](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L278-L292) termina con `return value if value >= 100 else None` (L292). Un abono de "50 pesos" se lee como ausencia de monto y el sistema vuelve a preguntar un dato que la persona ya dio.

### D-2 · Fechas reinterpretadas en silencio (viola INV-8)
[resolve_month#L295-L310](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L295-L310) (L307-L308) y [_explicit_months#L327-L338](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L327-L338) (L335-L336): `if num > today.month: y -= 1  # assume last year`. Un mes futuro ("diciembre", "enero") se convierte en el año pasado **sin declararlo**, en lugar de avisar de que no hay datos o que es futuro.

### D-3 · Fechas límite inválidas aceptadas por el MCP
[create_savings_goal_impl#L202-L205](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L202-L205) valida nombre e importe pero **no parsea `deadline`**; `update_savings_goal_impl` tampoco. La única validación de fecha está en la API ([routes.py#L55-L62](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L55-L62)) — **validación dispersa, viola INV-9**.

### D-4 · Límites de importe contradictorios entre capas (viola INV-9)
API: `≤ 10,000,000` ([routes.py#L52](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L52)). MCP: `≤ 100,000,000` ([finance_tools.py#L204-L205](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L204-L205)). El mismo dato tiene dos reglas distintas según el camino.

### D-5 · Proyecciones sin validación de montos
[_demo_projection#L1858-L1886](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1858-L1886): toma los dos primeros números ≥100 del texto (L1860-L1868) y llama a `project_savings`, que solo valida `monthly_amount > 0` ([finance_tools.py#L155-L166](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L155-L166)). No hay rechazo de montos excesivos, negativos ni de un destino imposible.

### D-6 · Productos y periodos que la persona no tiene
No existe verificación de tenencia ni de existencia de datos: el simulador de crédito responde para cualquier monto/plazo/producto ([routes.py#L147-L153](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L147-L153)), y un periodo sin datos se responde con el mes en curso en lugar de declarar "sin datos" (viola INV-6: nunca estimar ni inventar).

---

## 6. Clase E — Coherencia y formato

### E-1 · Texto y gráfica con bases distintas (viola INV-7)
- `spending_by_category` deriva el `pct` de la suma de gastos del periodo ([finance.py#L81-L88](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L81-L88)).
- El progreso de una meta usa el objetivo como base ([finance.py#L300](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L300) y [L346-L347](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L346-L347)).
- El `pct` de presupuesto usa el límite como base ([finance.py#L384](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L384)).
- La conclusión de tendencia usa el **primer mes** como base del cambio porcentual ([orchestrator.py#L958-L964](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L958-L964)) mientras la gráfica muestra todos los puntos.
Ninguna superficie **declara la base** del porcentaje, y no hay una función central que la calcule (no existe en [composer.py](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/composer.py)).

### E-2 · Tiempo verbal que no corresponde al periodo (viola INV-8)
[_demo_spending#L1009-L1012](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1009-L1012): "En {mes} **llevas** … de gastos" en presente, también para meses ya cerrados.

### E-3 · Afirmaciones estimadas, no consultadas (viola INV-6)
[_demo_overview#L1017-L1031](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1017-L1031) (L1022-L1023): "vas a mitad de la quincena" / "estamos cerca del cierre" se deriva de `date.today().day`, no del periodo consultado; si se pregunta por un mes pasado, la frase sigue hablando de hoy. Además `budget_overview.available` = `income - total_spent` ([finance.py#L392](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L392)) es una noción inventada que **no proviene del saldo disponible real**.

### E-4 · Formato no respeta lo pedido y el recálculo se duplica en el cliente
- Se responde con **gráfica** aunque se pidió un dato puntual: `_demo_spending` siempre devuelve `spending_chart_ui` ([orchestrator.py#L1007](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1007)).
- [BudgetPlanner.tsx#L20-L21](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/frontend/src/components/dynamic/BudgetPlanner.tsx#L20-L21) **recalcula** `spentTotal` y `available` (y el `pct` en L68) que ya vienen del servidor → puede divergir de la cifra del backend (viola INV-9).

### E-5 · Mensaje de confirmación genérico e incoherente
[routes.py#L180-L208](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L180-L208): `agent_confirm` construye el texto asumiendo `create_savings_goal` (`target_amount`, "quedó registrada con objetivo…") y fija `tools_used=["create_savings_goal"]` (L207) **aunque la acción pendiente fuera otra**.

---

## 7. Estado de los invariantes (evidencia)

| ID | Invariante | Estado | Evidencia |
|---|---|---|---|
| INV-1 | Transferencia no altera ingresos/gastos/categorías/balance/anomalías/pagos fijos | **Violado** | [finance_tools.py#L380-L385](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L380-L385) + base real (`Ahorro`, 22,500) |
| INV-2 | Saldo total = cuentas + metas; la transferencia no lo cambia | **Violado** | [finance.py#L23-L24](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L23-L24); 63,421.15 vs 112,621.15 |
| INV-3 | Disponible = saldo en cuentas; ±monto exacto por transferencia | **Parcial / frágil** | [finance_tools.py#L390](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L390) confunde disponible con total |
| INV-4 | Ahorrado ∈ [0, objetivo]; aportación ≤ falta y ≤ disponible | **Violado** | [finance.py#L319-L348](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L319-L348), [routes.py#L135-L144](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L135-L144) |
| INV-5 | Escritura atómica, idempotente, con confirmación de UI verificada en servidor | **Parcial** | idempotencia opcional ([L206](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L206)); `execute_pending` sin token ([L2277-L2286](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L2277-L2286)) |
| INV-6 | Toda cifra proviene de una consulta; si no hay dato se declara | **Violado** | [orchestrator.py#L1022-L1023](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1022-L1023), [finance.py#L392](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L392) |
| INV-7 | Todo porcentaje declara su base; texto y gráfica comparten base | **Violado** | bases distintas en [finance.py#L87](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L87), [#L300](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L300), [#L384](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/finance.py#L384) |
| INV-8 | Fechas inválidas/futuras/sin datos se declaran; el tiempo verbal respeta el periodo | **Violado** | [orchestrator.py#L307-L308](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L307-L308), [#L1009](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L1009) |
| INV-9 | Métricas derivadas en una única capa de dominio | **Violado** | validación duplicada ([routes.py#L47-L64](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/api/routes.py#L47-L64) vs [finance_tools.py#L202-L205](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L202-L205)); recálculo en [BudgetPlanner.tsx#L20-L21](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/frontend/src/components/dynamic/BudgetPlanner.tsx#L20-L21) |

---

## 8. Infraestructura exigida que hoy no existe

| Requisito | Estado |
|---|---|
| `docs/DOMAIN.md` con el modelo e invariantes | **No existe** |
| Tipo `transferencia` en la base + restricciones (CHECK/trigger) | **No existe** |
| Función central de validación de dominio | **No existe** (validación dispersa) |
| Libro de movimientos con tres tipos | **No existe** (solo `income`/`expense`) |
| Migración/reparación de datos inconsistentes | **No existe** (y la base ya está inconsistente) |
| `scripts/reset-demo.cmd` + endpoint demo con semilla determinista | **No existe** (hay `setup.cmd`, `start-all.cmd`, `stop-all.cmd`, `run-tests.cmd`) |
| Script de reconciliación de INV-1…INV-4 sobre la base real | **No existe** |
| Prueba de concurrencia (confirmaciones simultáneas) | **No existe** |
| Pruebas de propiedades (INV-1…INV-4 aleatorias) | **No existe** |
| Registro estructurado con `trace_id` sin datos sensibles | **Existe** ([structured_logging.py](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/core/structured_logging.py), `trace_id` en [orchestrator.py#L2291-L2299](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/app/services/agent/orchestrator.py#L2291-L2299)) |

---

## 9. Plan propuesto para completar la Fase 1 (a tu aprobación)

Orden acordado por dependencia, no por comodidad:

1. **`docs/DOMAIN.md`** — modelo de dominio (tipos de movimiento), INV-1…INV-9 con su interpretación operativa y la definición de "gasto", "disponible", "saldo total".
2. **Capa única de dominio** — en `finance.py`: agregados que excluyan transferencias por construcción; `total_balance()` = cuentas + metas; `available_balance()` = cuentas; función central de validación (nombre, monto, fecha límite, límites de meta). Eliminar la validación paralela de `routes.py`/`finance_tools.py` (que solo invocan a la central).
3. **Esquema y migración** — añadir el tipo/estructura de transferencia y las restricciones (CHECK/trigger) que hagan **imposible** por base lo que hoy se hace por convención; migrar el dato existente `type='expense', category='Ahorro'` por 22,500 a un movimiento de transferencia (reparando el gasto, la categoría y el balance del mes de ese periodo).
4. **Semilla determinista + reset** — `scripts/reset-demo.cmd` y endpoint solo en modo demo, semilla idéntica en cualquier máquina.
5. **Reconciliación** — script que verifica INV-1…INV-4 sobre la base real y falla con detalle por invariante y por fila.
6. **Corrección de Clase A** en el camino de escritura ([finance_tools.py#L268-L399](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/mcp-server/tools/finance_tools.py#L268-L399)) y en el frontend (`+`/`−` de tres tipos).
7. **Pruebas de Fase 1** — ledger, INV-4, idempotencia, atomicidad, migración idempotente, reconciliación en verde. Ajuste de las pruebas que hoy **codifican el modelo incorrecto** (p. ej. [test_mcp_tools.py#L114](file:///C:/Users/jonna/OneDrive/Escaneos/Escritorio/BANORTE-IA-FINANZAS/proyecto-banorte-ai-finanzas/backend/tests/test_mcp_tools.py#L114) afirma que un abono reduce `total_balance`, cuando INV-2 exige lo contrario).

**Criterios de aceptación de Fase 1:** suite y build en verde; reconciliación de INV-1…INV-4 en verde sobre la base real y sobre una base recién sembrada; base existente migrada sin pérdida; ningún recálculo de métricas fuera de la capa de dominio.

---

## 10. Decisiones que necesito de ti antes de tocar la base

1. **Alcance de la migración de datos**: reparar el abono ya registrado como gasto (22,500 en «Compra planeada») convirtiéndolo en transferencia — ¿correcto?, o ¿prefieres reconstruir la demo desde cero con la semilla determinista y tratar `banorte.db` como desechable?
2. **`docs/AUDITORIA-FASE1.md`**: lo entrego aquí; si prefieres, lo muevo a `docs/` del repositorio junto con `DOMAIN.md`.
3. **Confirmación de que la Fase 1 completa se ejecute en un solo tramo** (puntos 1–7) o que quieres revisar `docs/DOMAIN.md` y el diseño de la migración **antes** de aplicarlos.

---

### Declaración de estado
**No se ha modificado ningún archivo del proyecto.** Este informe es solo diagnóstico. Las Clases B, C, D y E se corregirán en las Fases 2 y 3, conforme a tu secuencia; aquí se documentan porque comparten la misma causa raíz estructural (reglas de dominio dispersas) que la Clase A.
