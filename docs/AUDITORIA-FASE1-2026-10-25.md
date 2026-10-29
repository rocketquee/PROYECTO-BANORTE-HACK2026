# Informe de auditoría — Fase 1 (estado actual)

### Proyecto: `proyecto-banorte-ai-finanzas` (prototipo educativo, datos sintéticos, SQLite)
### Rol: ingeniero senior de IA / integridad de datos / empaquetado de escritorio
### Fecha: 2026-10-25 · Alcance: Clases A–E, entregables de Fase 1 (capa de proveedor,
### salud, indicador, respaldo) y restricción nueva de empaquetado .exe · **Solo diagnóstico: no se modificó código**

Este informe continúa y actualiza `docs/AUDITORIA-FASE1.md` (2026-10-22). Aquel definió las
Clases A–E y un plan; desde entonces se aplicó **una parte** de ese plan. Aquí se reporta el
estado real de hoy, las instancias **nuevas** de las Clases A–E que introdujo (o dejó abiertas)
esa aplicación parcial, y el estado de los entregables de IA de la Fase 1.

---

## 0. Método

- Lectura directa de: `backend/app/core/config.py`, `database.py`, `migrate.py`, `seed.py`,
  `backend/app/main.py`, `backend/app/api/routes.py`, `backend/app/schemas/api.py`,
  `backend/app/services/finance.py`, `backend/app/services/agent/providers.py`,
  `backend/app/services/agent/orchestrator.py`, `backend/app/services/mcp_client.py`,
  `mcp-server/tools/finance_tools.py`, `frontend/src/components/AgentView.tsx`, `frontend/src/lib/api.ts`.
- Ejecución de la suite: `..\.venv\Scripts\python -m pytest tests -q` en `backend/`.
- Inspección del árbol del repositorio (`scripts/`, `.github/`, `docs/`, `frontend/`).
- Sin escrituras en base ni cambios de código.

---

## 1. Resumen ejecutivo

Tres hallazgos condicionan toda la Fase 1:

1. **La suite está en rojo: 10 fallos de 255 pruebas.** No son fallos de la capa de IA: son el
   resto de una **migración de dominio a medias** (el modelo pasó a un libro con tipo
   `transfer` — INV-1…INV-4 — pero sus consumidores siguen llamando la API antigua). El estado
   base hoy **no cumple** el criterio de Fase 1 «suite y build en verde».
2. **Los entregables de IA de la Fase 1 ya existen en gran medida**: capa de proveedor
   (`providers.py`), indicador visible (`mode: demo|live` en la interfaz) y respaldo (ruta
   `demo_response` + degradación ante `ProviderError`). Lo que falta es la **verificación de
   salud del proveedor** (el `/health` actual solo mira el MCP), la **versión de la app** en la
   interfaz y cerrar huecos de los otros entregables.
3. **La restricción de empaquetado .exe no se cumple.** `DB_PATH` apunta dentro del repositorio
   (`backend/data/banorte.db`) y no existe una función única de resolución de rutas hacia la
   carpeta de datos del usuario; las migraciones **no** corren al iniciar; no hay reset/restablecer
   con ruta configurable.

---

## 2. Qué cambió desde el informe del 2026-10-22

El plan del informe anterior se aplicó **parcialmente**:

| Pieza del plan anterior | Estado hoy | Evidencia |
|---|---|---|
| `docs/DOMAIN.md` con modelo e invariantes | **Existe** | `docs/DOMAIN.md` |
| Diseño de la migración | **Existe** | `docs/MIGRACION-FASE1.md` |
| Tipo `transfer` en el esquema + restricciones | **Existe** | `seed.py` (`TRANSACTIONS_DDL`, `TRIGGERS`) |
| Capa de dominio única (`finance.py`) con INV-1…INV-4 | **Parcial** | `finance.py` (list/update_goal nuevos) |
| Migración idempotente con respaldo y comprobaciones | **Existe, pero solo por CLI** | `migrate.py` (`MIGRATION_KEY`) |
| Semilla determinista con fondeo por transferencia | **Existe** | `seed.py` (`SEED_TRANSFERS`, `BANORTE_DEMO_TODAY`) |
| `scripts/reset-demo.cmd` + endpoint demo | **No existe** | `scripts/` no lo contiene |
| Reconciliación INV-1…INV-4 | **No existe** | sin script |
| Corregir Clase A en el camino de escritura | **Incompleto** | ver §4 |
| Pruebas de Fase 1 / actualizar pruebas que codifican el modelo viejo | **Incompleto** | 10 fallos (§3) |

**Conclusión:** el cambio de modelo se hizo «por dentro» (esquema + `finance.py`) pero
**no se propagó a los bordes** (herramientas MCP, rutas REST, contratos y pruebas). Eso es la
causa única de la mayoría de los fallos actuales.

---

## 3. Estado de la suite (evidencia)

```
..\.venv\Scripts\python -m pytest tests -q
→ 10 failed, 245 passed in 83.97s
```

Fallos y causa raíz:

| Prueba | Causa raíz |
|---|---|
| `test_mcp_tools.py::test_get_transactions_filters` | `finance_tools.py:48` ordena `categories` que ahora incluyen `None` (las transferencias tienen `category=NULL`) → `TypeError` |
| `test_bugfixes.py::TestR02Timeline::test_timeline_component` | mismo `TypeError` (`finance_tools.py:48`) |
| `test_bugfixes.py::TestR02Timeline::test_timeline_variants` | mismo `TypeError` |
| `test_bugfixes.py::TestBug003NoInfoLeak::test_no_technical_strings_in_answers[Muéstrame mis movimientos]` | dependiente de la ruta de movimientos degradada |
| `test_mcp_tools.py::test_update_goal_validation` | `finance_tools.py:260` llama `update_goal(saved_amount=…)`, argumento que ya no existe |
| `test_mcp_tools.py::test_savings_contribution_*` (3 pruebas) | camino de aportación sobre `update_goal` con API antigua |
| `test_services.py::test_goal_create_update_persists` | `update_goal(add_amount=…)`, argumento que ya no existe |
| `test_purchase_plan.py::test_purchase_plan_to_goal_uses_real_mcp_and_persists` | mismo desajuste en la composición MCP |

**Patrón único:** el contrato de la capa de dominio cambió (`update_goal` ya no acepta
`saved_amount`/`add_amount`; el ahorrado solo cambia por transferencias) y los llamadores no.

---

## 4. Clases A–E: instancias **nuevas** (auditoría completa del sistema)

### Clase A — Integridad contable

- **A-12 · El tipo `transfer` rompe a los consumidores de categorías.**
  `mcp-server/tools/finance_tools.py:48` y `backend/app/api/routes.py:105` hacen
  `sorted({t["category"] …})`. Como las transferencias nuevas tienen `category=NULL`, el
  `sorted` compara `str` con `None` y **lanza `TypeError`**: hoy `GET /transactions` y la
  herramienta de movimientos pueden fallar en tiempo de ejecución. Misma clase que A-6
  (propagación del tipo a todos los agregados), instancia nueva.

- **A-13 · `PATCH /goals/{id}` está muerto en ejecución.**
  `routes.py:136-141` llama `finance.update_goal(…, add_amount=body.add_amount, …)`, pero
  `finance.update_goal` (`finance.py:368`) ya **no** acepta `add_amount`. Cualquier edición de
  meta por REST lanza `TypeError` (500). Es la ruta que el propio informe anterior citaba como
  una de «tres puertas» para violar INV-4; ahora además está rota.

- **A-14 · `POST /goals` sigue aceptando `saved_amount` del cliente (viola INV-4).**
  `routes.py:128` pasa `saved_amount=body.saved_amount` a `create_goal`, y
  `GoalCreateRequest.saved_amount` (`schemas/api.py:22`) es entrada directa del cliente.
  Bajo el modelo nuevo el ahorrado **solo** cambia por transferencias (INV-4); permitir que el
  cliente lo fije al crear reabre la puerta que la migración quiso cerrar.

- **A-15 · `update_savings_goal` sigue escribiendo `saved_amount` por la puerta trasera.**
  `finance_tools.py:260` construye `update_goal(saved_amount=…)`. Además de romper (A-13), es la
  vía que el informe anterior señalaba sin idempotencia ni validación (INV-4/INV-5).

- **A-16 · El contrato REST no expone `transfer`.**
  `routes.py:100-101` (`GET /transactions`) restringe `type` a `income|expense`, y
  `finance.list_transactions` (`finance.py:75`) solo filtra si `tx_type in LEDGER_TYPES`. El tipo
  nuevo existe en la base pero es **invisible** en la API: la reconciliación de INV-1…INV-4 no se
  puede verificar desde fuera.

### Clase B — Prioridad de interpretación
Sin cambios desde el informe anterior (B-1…B-6 siguen vigentes). La migración no tocó
`detect_intent`. **No hay instancias nuevas.**

### Clase C — Consultas que no se resuelven
Sin cambios (C sigue vigente). No hay instancias nuevas; corresponde a la Fase 2.

### Clase D — Validación
- **D-7 (nueva) · La validación de metas sigue dispersa y ahora además es inconsistente con el
  dominio.** `GoalUpdateRequest.add_amount` (`schemas/api.py:28`) y `GoalCreateRequest.saved_amount`
  validan rangos en el esquema, pero la capa de dominio ya no acepta esos campos: la regla de
  INV-4 dejó de ser verificable porque el contrato REST describe una operación que el dominio
  ya prohíbe. Refuerza D-4 y INV-9 (validación duplicada y contradictoria entre capas).

### Clase E — Coherencia y formato
- **E-6 (nueva) · `agent_confirm` sigue asumiendo `create_savings_goal`.** `routes.py:186-208`
  deriva el mensaje y fija `tools_used=["create_savings_goal"]` sin mirar la acción pendiente
  real (ya señalado como E-5); tras el cambio de modelo, el texto «quedó registrada con
  objetivo…» describe una operación que puede no haber ocurrido. Sigue abierto.

---

## 5. Restricción nueva de empaquetado (.exe) — estado

| Requisito | Estado | Evidencia |
|---|---|---|
| Ruta resuelta por **una sola** configuración (por defecto carpeta de datos del usuario) | **No cumple** | `config.py:5-9`: `BASE_DIR`/`ROOT_DIR` desde `__file__`, `DB_PATH` por defecto `backend/data/banorte.db` (dentro del repo) |
| Nunca junto al ejecutable ni en el repo | **No cumple** | mismo punto |
| Se crea y siembra sola en el primer arranque | **Parcial** | `database.ensure_db()` siembra si `accounts` está vacía, pero escribe en `DATA_DIR` del repo |
| Migraciones automáticas e **idempotentes al iniciar** | **No cumple** | `migrate.py` solo corre por CLI; `main.py` (`lifespan`) llama `ensure_db()` y **no** `migrate()` |
| Respaldo antes de modificar | **Parcial** | `migrate.backup()` lo hace, pero solo si se invoca la migración por CLI |
| Reset y reconciliación con ruta **configurable** | **No cumple** | no hay endpoint/script de reset ni reconciliación; `migrate.py` sí acepta `db_path` (base reutilizable) |
| Sin dependencias del entorno (localhost fijo, puertos fijos, OneDrive, estructura del repo) | **No cumple** | `FRONTEND_ORIGIN=http://localhost:3000` (`config.py:25`); `MCP_SERVER_PATH` derivado del repo; `load_dotenv` lee `.env` del repo |
| Pruebas de migración y de reset con ruta configurable | **No cumple** | no existen |

**Nota:** `migrate.migrate(db_path, dry_run)` ya acepta una ruta arbitraria — es el cimiento
correcto para «reset y reconciliación con ruta configurable». Falta la pieza que lo invite desde
el arranque y desde un endpoint de reset, con la ruta resuelta por una única función.

---

## 6. Entregables de IA de la Fase 1 — estado y huecos

| Entregable | Estado | Evidencia | Hueco a cerrar |
|---|---|---|---|
| **Capa de proveedor** | **Existe** | `providers.py`: `OpenAIProvider`, `AnthropicProvider`, `get_provider()`, `provider_mode()`, `ProviderTurn` validado con Pydantic | Sin sonda de salud del proveedor; sin detección explícita de «modelo sin soporte de herramientas» |
| **Verificación de salud** | **Parcial** | `routes.py:81-86` `GET /health` devuelve `status`/`services` según `mcp_client.available` | No reporta estado del **proveedor** de IA, ni de la base, ni el `mode`; sin versión de app |
| **Indicador visible** | **Existe** | `AgentView.tsx:273-282`: texto por mensaje para `mode==="demo"` y `mode==="live"` | Es por mensaje, no un indicador de estado/«respaldo activo»; falta la **versión** de la app en la interfaz |
| **Respaldo (reglas)** | **Existe** | `orchestrator.py:2329-2344`: sin proveedor o `AI_PROVIDER=demo` → `demo_response`; ante `ProviderError` → cae a `demo_response` con aviso y `mode="demo"` | Ver `docs/LLM.md`, `.env.example` de proveedor y evaluación (Fases 3–4) |

**Conclusión:** de los cinco puntos de la Fase 1, tres existen (proveedor, indicador, respaldo) y
uno existe a medias (salud). El trabajo real de la Fase 1 es: (a) **sanear la base roja** de §3,
(b) **completar la salud** y la versión, y (c) **cumplir la restricción de empaquetado** de §5.

---

## 7. Requisitos de IA (verificador, seguridad, respaldo) — estado

- **Verificador de fundamentación (antiinvención):** no existe como componente; pertenece a la
  Fase 3.
- **Seguridad — datos, no instrucciones:** hay guardas de inyección por regex
  (`orchestrator.py:374-402`) pero son de Clase B (falsos positivos), no un aislamiento
  sistemático de «resultados de herramientas como datos».
- **Seguridad — enmascarado:** hay nota de minimización en tarjetas
  (`finance_tools.py:57`, solo últimos 4 dígitos) y logs estructurados sin contenido de usuario
  (`structured_logging.py`, `trace_id`). Falta política de enmascarado antes de enviar al modelo.
- **Seguridad — sin claves en el repo:** `config.py` lee claves solo de entorno; `.env` no está
  versionado con valores reales. **Correcto hoy**, pero la entrega .exe exigirá el almacén seguro
  del sistema (Fase 5).
- **Aviso educativo permanente:** presente en respuestas de conversación y en textos de sección.
- **Respaldo:** existe (§6) y comparte el contrato `ChatResponse` con la ruta en vivo.

---

## 8. Decisiones que necesito de ti antes de tocar código

1. **La base roja (§3).** ¿Autorizas que la Fase 1 incluya **terminar la propagación del modelo
   `transfer`** a los bordes (herramientas MCP, `GET/PATCH/POST /goals`, `GET /transactions`) y
   **actualizar las pruebas que codifican el modelo viejo** —que es lo que exige el criterio
   «suite en verde»? Sin esto, cualquier trabajo de la capa de IA se construye sobre rojo.
2. **Reparar vs. resembrar.** `banorte.db` en el repo ya está migrado por la semilla nueva; para
   el paquete .exe la base vivirá en la carpeta del usuario. ¿Prefieres tratar la base del repo
   como **desechable** (borrar y dejar que el primer arranque cree/siembre/migre) o conservar la
   ruta de migración con respaldo sobre una base existente?
3. **Alcance de rutas.** ¿Confirmas que la resolución única de rutas use `%LOCALAPPDATA%` (o
   `%APPDATA%`) con override por variable de entorno, y que `FRONTEND_ORIGIN`/puerto dejen de ser
   constantes fijas ya en esta fase (aunque el lanzador .exe sea Fase 5)?
4. **Orden de la Fase 1.** Propongo: (1) sanear la base roja terminando la propagación del modelo
   `transfer`; (2) cerrar §5 (rutas + migración/seed/reset idempotentes con ruta configurable);
   (3) completar salud + versión + indicador. ¿Lo ejecuto en ese orden en un solo tramo, o
   prefieres revisar el diseño de rutas/migración antes de aplicarlo?

---

## 9. Declaración de estado

**No se ha modificado ningún archivo del proyecto ni ningún dato.** Este informe es solo
diagnóstico. Las Clases B, C y D y el verificador de fundamentación corresponden a las Fases 2 y
3 según tu secuencia; aquí se documentan porque comparten la causa raíz estructural (reglas de
dominio dispersas entre capas) con la Clase A.
