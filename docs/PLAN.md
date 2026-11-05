# PLAN DE TRABAJO — Etapas 2 a 9

**Proyecto:** `proyecto-banorte-ai-finanzas`
**Base auditada:** rama `main`, commit `7062c60`
**Fecha del plan:** 2026-10-30
**Documento de estado:** [ESTADO-PROYECTO.md](./ESTADO-PROYECTO.md)

---

## Regla de avance

Ninguna etapa se cierra por "código escrito": se cierra con una comprobación reproducible y con la evidencia registrada. No se avanza a la Etapa 3 con la reconciliación contable en rojo. Los datos reales se reparan solo con copia de seguridad previa verificada, transacción y plan de reversa.

La Etapa 1 (modelo de dominio, centavos, migraciones, contrato UI, pruebas base) está **parcialmente construida**, pero sus criterios de aceptación **no se cumplen** por los defectos descritos en `ESTADO-PROYECTO.md`. Por eso las Etapas 2 y 3 son correctivas y bloquean al resto.

---

## Estado global

| Etapa | Nombre | Estado | Depende de | Punto de entrada |
|---|---|---|---|---|
| 1 | Integridad contable base | **Parcial / roja** | — | `apply_transfer`, triggers, reconciliación |
| 2 | Reparación y reconciliación del libro | **2.1–2.9 cerradas; 2.5 real ejecutada (sin cambios)** | 1 | `backend/app/core/ledger_repair.py` |
| 3 | Validación única y paridad REST/MCP | **Pendiente** | 2 | `backend/app/services/domain.py`, `routes.py` |
| 4 | IA: fundamentación, privacidad y confirmaciones | **Hecho (4.1–4.6)** | 2, 3 | `backend/app/services/agent/orchestrator.py` |
| 5 | UI/UX: contrato en ejecución y ciclo cerrado | **Pendiente** | 3, 4 | `frontend/src/components/dynamic/DynamicRenderer.tsx` |
| 6 | Calidad: propiedades, concurrencia, E2E y CI | **Pendiente** | 2–5 | `backend/tests/`, `frontend/tests/` |
| 7 | Portabilidad y empaquetado | **Pendiente** | 2, 3, 6 | `scripts/`, `vercel.json`, `mcp-server/` |
| 8 | Documentación y limpieza del repositorio | **Pendiente** | 2–7 | `README.md`, `docs/` |
| 9 | Entrega, aceptación y operación | **Pendiente** | 2–8 | checklist de aceptación |

---

## Etapa 2 — Reparación y reconciliación del libro

**Objetivo:** que una meta no pueda quedar marcada como completa sin estarlo, que toda aportación válida se pueda aplicar, y que la reconciliación detecte cualquier diferencia entre el libro y las metas.

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 2.1 | Corregir el orden y el doble conteo de `apply_transfer` | **Hecho** | `finance.py:529-561` calcula `new_saved_cents` una sola vez e inserta la transferencia antes de actualizar el ahorrado; `tests/test_transfer_accounting.py` cubre 50%, 51%, 60%, 100%, retiro y API | Aportar el 100% restante marca la meta como completada; aportar 60% no falla; aportar 50% **no** la marca completada |
| 2.2 | Corregir el trigger de transferencias | **Hecho** | `finance.py:550-561` inserta la transferencia antes del `UPDATE`; el trigger `seed.py:123-133` compara contra el estado previo; prueba de aportación exacta y retiro | El trigger valida contra el estado previo y el orden de escritura ya no lo duplica; no hay 500 en ningún monto válido |
| 2.3 | Reconciliar `saved_amount` contra `SUM(transfers)` | **Hecho** | `reconcile.py` invariantes `goal_ledger`, `goal_status`, `orphan_transfers`; `tests/test_reconcile.py` (11 pruebas) reproduce las diferencias +$18,500 / -$14,300 / +$22,500 con meta y monto | `reconcile` falla con fila, meta y diferencia; se agrega a la suite |
| 2.4 | Reconciliar estado contra objetivo | **Hecho** | `reconcile.py` exige `completada ⇒ saved == target` y `saved == target ⇒ completada`; pruebas de borde en `tests/test_reconcile.py` | `status='completada'` exige `saved_amount == target_amount`; prueba de borde |
| 2.5 | Reparar la base real con migración versionada | **Hecho (base real, 2026-11-04)** | `backend/app/core/ledger_repair.py` (plan/apply, `BEGIN IMMEDIATE`, respaldo + SHA-256, auditoría); ejecutado con `--apply --allow-real`: respaldo verificado `backend/data/backups/banorte.db.bak-20261104-221035`, SHA-256 `b4bb7220…f8366`, `integrity_check=ok`, FK `[]`; `ledger-v3` no requirió cambios (0 swaps, 0 piernas, 0 aperturas), `ids_afectados=[]`; `reconcile` antes/después `ok=true`, `failures=0`, 13 invariantes. Auditoría: `docs/AUDITORIA-LEDGER-V3-20261104-221035.json` | Corregir el `INSERT` de `ledger-v1` y su verificación por fila; migración `ledger-v3` con respaldo verificado deja los tres saldos y el movimiento 967 consistentes; `reconcile` verde |
| 2.6 | Corregir el fondeo de la semilla | **Hecho** | `seed.py` inserta metas con `saved=0` y las fondea con `finance.apply_transfer`; `tests/test_transfer_accounting.py` verifica que toda meta con ahorro tiene libro y que dos siembras dan el mismo SHA-256 | Toda meta sembrada con ahorro > 0 tiene su transferencia; base nueva reconcilia al 100% |
| 2.7 | Registrar todas las cuentas debitadas | **Hecho** | `TRANSFER_LEGS_DDL` + `transfer_legs`; `_debit_accounts_cents` devuelve todas las piernas y `apply_transfer` las inserta; `tests/test_transfer_accounting.py` cubre multi-cuenta y reconstrucción por cuenta | Una transferencia multi-cuenta conserva todas las piernas y permite reconstruir cada saldo |
| 2.8 | Congelar el calendario de la semilla | **Hecho** | `DEFAULT_REFERENCE_DATE = 2026-10-30`; `BANORTE_DEMO_TODAY` lo sobrescribe; `tests/test_transfer_accounting.py` compara SHA-256 de dos siembras | Semilla reproducible con fecha fija por defecto o documentada como variable obligatoria |
| 2.9 | Fecha de referencia única en datos, herramientas y pruebas | **Hecho** | `seed.py:251` expone `reference_today()`; la usan `finance._today()`, `domain.py:135,149`, `reconcile.py:253`, `ledger_repair.py:358`, MCP (`finance_tools.py:74,90,96,187`), `composer.py:280,285`, `orchestrator.py` y las pruebas. `grep date.today()` en `backend` y `mcp-server` → 0 | Semilla, backend, MCP y pruebas comparten el mismo "hoy"; sin `date.today()` ni fechas literales; suite 319 en verde |

**Aceptación de Etapa 2**

1. Base nueva: completar una meta funciona; al 50% sigue activa; `reconcile` verde.
2. Base real reparada (**ejecutada y verificada 2026-11-04**): metas 1–4 cuadran con el libro; movimiento 967 apunta a la meta correcta. La copia ya cumple.
3. Aportación multi-cuenta reconstruible por cuenta.
4. Suite backend (317) y build de frontend en verde, con pruebas nuevas de borde.

**Archivos principales:** `backend/app/services/finance.py`, `backend/app/core/seed.py`, `backend/app/core/reconcile.py`, `backend/app/core/migrate.py`, `backend/tests/test_savings_contribution.py`.

---

## Etapa 3 — Validación única y paridad REST/MCP

**Objetivo:** una sola autoridad de validación; los dos transportes aceptan y rechazan exactamente lo mismo; ningún dato inválido entra por PATCH ni por MCP.

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 3.1 | Validar `status` con dominio cerrado | **Hecho** | `GoalStatus = Literal["activa","completada"]` (`api.py:28,38`); `domain.validate_goal_status` y `domain.update_goal` (`domain.py:121-132,264-281`); PATCH usa la capa única y traduce a 422 (`routes.py:234-244`); MCP usa `domain.update_goal` (`finance_tools.py:339`); CHECK en DDL (`seed.py:99`) y migración `goal-status-v1` (`migrate.py:43,695`); 4 pruebas (`test_goal_validation.py:29-66`) | `status` es `Literal` y la base tiene CHECK; valor inválido devuelve 422 |
| 3.2 | Validar fecha límite en PATCH y MCP | **Hecho** | `domain.validate_deadline` (`domain.py:138`); `domain.update_goal` valida antes de escribir (`domain.py:264-281`); PATCH traduce a 422 (`routes.py:237-242`); MCP delega en el dominio (`finance_tools.py:339`); catálogo MCP usa la misma función (`mcp_catalog.py:48-54`); 6 pruebas (`test_goal_validation.py:69-124`) | Fecha inválida o pasada devuelve 422 en REST y error de herramienta en MCP |
| 3.3 | Sanitizar y limitar el nombre en toda escritura | Pendiente | `routes.py:46-64` solo sanea POST; `PATCH` guarda `<script>alert(1)</script>` (200); MCP no sanea | Toda creación/edición pasa por la misma función de dominio |
| 3.4 | Unificar límites REST/MCP | Pendiente | REST: $10,000,000 (`routes.py:58-62`); MCP: $100,000,000 (`finance_tools.py:207`) | Un solo límite probado en ambos transportes |
| 3.5 | Igualar capacidades de transferencia | Pendiente | REST acepta `goal_to_account` (`savings.py`); MCP fija `account_to_goal` (`finance_tools.py:288-297`) | Misma matriz de direcciones o diferencia documentada y probada |
| 3.6 | Convertir errores de validación en 4xx | Pendiente | `PATCH` con objetivo menor a lo ahorrado lanza `ValueError` sin captura; presupuesto 0 devuelve 500 (`budget_update`, `finance.py:597`) | Ningún dato de usuario produce 500; todos los rechazos son 409/422 con mensaje |
| 3.7 | Validar presupuesto | Pendiente | `schemas/api.py:48` permite 0, la tabla exige `> 0` (`seed.py:96-101`); categoría arbitraria se inserta (200) | 0 se rechaza o se interpreta como borrar; categoría se valida contra la taxonomía |
| 3.8 | Pruebas de paridad | Pendiente | No hay suite que compare REST y MCP | Tabla de casos idénticos ejecutada contra ambos |

**Aceptación de Etapa 3:** no existe escritura que evite `domain.py`; REST y MCP comparten límites, saneamiento y validación de fechas/estado; pruebas de paridad y de errores 4xx en verde.

---

## Etapa 4 — IA: fundamentación, privacidad y confirmaciones

**Objetivo:** que el modo en vivo no invente cifras, no filtre datos personales y no permita confirmaciones reutilizables o ajenas.

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 4.1 | Verificador de fundamentación | **Hecho** | `ground_check()` extrae cifras y las contrasta con `tool_results` (`orchestrator.py:262-280`); la integración corrige `sin_dato`, reintenta una vez y sustituye por respuesta determinista (`orchestrator.py:2486-2533,2556`); pruebas en `test_agent_grounding.py:72-108` | Toda cifra del texto debe existir en una herramienta; si no, se sustituye por respuesta determinista |
| 4.2 | Minimización de datos antes del proveedor | **Hecho** | `_mask_tool_result()` redacta nombres, correos, teléfonos, números largos y etiquetas sensibles antes de enviar el resultado al modelo (`orchestrator.py:322-336,2447`); prueba de fuga en `test_agent_grounding.py:167-185` | Los nombres y datos no necesarios se redactan antes de salir; prueba de fuga |
| 4.3 | Inventario y limpieza de PII | **Hecho** | 11 archivos versionados saneados (`.archify/...`, `docs/arquitectura.*.json`, `docs/AUDITORIA-FASE1*.md`, `docs/DATA-DICTIONARY.md`, `docs/bitacora.../Pendientes.md`); `backend/data/banorte.db` y respaldos regenerados sin PII; guardia `test_no_pii.py:41-77`; `git grep` sin coincidencias | Base de entrega sin PII; repositorio sin rutas personales; política documentada |
| 4.4 | Confirmaciones con vigencia y alcance | **Hecho** | Store persistente con hash, TTL de 30 min, binding sesión/principal/trace, consumo atómico y replay (`confirmations.py:15,33,42,81,131,143`); tabla y migración `confirm-v1` (`seed.py:119-133`, `migrate.py:121-122,478-484`); `register_pending`/`execute_pending` (`orchestrator.py:2668-2707`); error tipado a 410/409 (`routes.py:242-246`); `session_id` obligatorio (`api.py:126-128`); 9 pruebas (`test_confirmations.py:35-170`) | Token de un solo uso, TTL, ligado a sesión/trace y probado contra replay |
| 4.5 | Autenticación si se publica | **Hecho** | Cookie de sesión firmada, PBKDF2 y CSRF de doble envío (`auth.py:54-257`); sesiones persistentes y migración `auth-v1` (`seed.py:135-146`, `migrate.py:43,487-500`); login/me/logout con rate limit (`routes.py:49,109-149`, `api.py:131-133`); middleware fail-closed y CORS con credenciales (`main.py:30,62-90`); frontend `AuthGate` y `credentials: include` (`api.ts:24-75`, `AuthGate.tsx:15-75`, `layout.tsx:18`); 5 pruebas (`test_auth.py:29-138`) | Local sigue sin auth; público exige auth, cookie Secure y CSRF; sin secretos en repo |
| 4.6 | Inyección de prompt con datos | **Hecho** | Proveedor falso recibe datos maliciosos en `category`/`description`/nombre de meta y luego intenta `create_savings_goal` con `confirm=true`; el orquestador fuerza `confirm=False` y solo registra confirmación (`test_agent_injection.py:89-132`); herramienta fuera de allowlist se rechaza sin llamar MCP (`test_agent_injection.py:238-259`); UI y eco del modelo se sanean (`orchestrator.py:595-617,2350-2377,2561-2566`); los `params` de la confirmación pendiente también se sanean (`orchestrator.py:2461`; `test_agent_injection.py:134-164`); solo `/agent/confirm` ejecuta el token (`test_agent_injection.py:262-303`); prueba demo ya no es vacua (`test_bugfixes.py:210-218`); guardas `_mask_tool_result`/allowlist (`orchestrator.py:322-336,2640-2642`) | El modelo no gana herramientas ni escrituras; la inyección queda como dato, se redacta en UI y requiere confirmación explícita |

---

## Etapa 5 — UI/UX: contrato en ejecución y ciclo cerrado

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 5.1 | Validar el contrato en el cliente | Pendiente | `chatStore.ts:97-105` hace `JSON.parse` y un cast; `DynamicRenderer` solo comprueba el tipo | Validación runtime de `ChatResponse`/`UISpec`; un localStorage manipulado no rompe la pantalla |
| 5.2 | Cerrar el ciclo o etiquetar lo informativo | Pendiente | Solo compra y aportación envían `ui_event`; otras tarjetas solo mandan preguntas de texto (`SpendingChart.tsx:71`, `CreditSimulator.tsx:115`); filtros y toggles no vuelven; README:20 generaliza | Cada control tiene retorno al agente o se marca explícitamente como solo lectura |
| 5.3 | Una sola semántica de "disponible" | Pendiente | `finance.py:633` y `BudgetPlanner.tsx:20-21` usan ingreso − gasto; `DOMAIN.md:116` define disponible = saldo en cuentas | El servidor calcula una vez; el cliente muestra, no recalcula |
| 5.4 | Accesibilidad medida | Pendiente | Solo hay declaraciones; no hay axe/Lighthouse ni pruebas de teclado | axe sin errores críticos, foco visible, contraste y lectores de pantalla |
| 5.5 | Pruebas de componentes y navegador | Pendiente | `frontend/tests/*.test.mjs` lee archivos y compara regex; no renderiza componentes | Al menos un E2E de compra, aportación, presupuesto y recarga |

---

## Etapa 6 — Calidad: propiedades, concurrencia, E2E y CI

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 6.1 | Propiedades de dinero e invariantes | Pendiente | La suite actual (302) cubre 2.1, pero no tiene property-based ni concurrencia | Property-based tests de aportaciones, retiros, redondeo y reconciliación |
| 6.2 | Concurrencia real | Pendiente | No hay prueba de dos confirmaciones simultáneas; `BEGIN IMMEDIATE` ayuda, pero `execute_pending` no bloquea | Dos confirmaciones concurrentes producen un solo movimiento |
| 6.3 | Migración y respaldo | Pendiente | No hay prueba de restaurar un respaldo ni de migrar una base vieja | Migración idempotente, respaldo restaurable y checksum verificado |
| 6.4 | CI | Pendiente | `.github/workflows/` no existe; solo está el árbol vendido `.github/skills/archify` | Pipeline con lint, typecheck, tests, build y base temporal |
| 6.5 | Lint y cobertura | Pendiente | `package.json` no tiene `lint`; no hay ruff/eslint/coverage | Comandos únicos documentados y umbral mínimo |

---

## Etapa 7 — Portabilidad y empaquetado

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 7.1 | Fijar dependencias | Pendiente | `backend/requirements.txt` usa `>=`; `package.json` usa `^`; `@next/swc-win32-x64-msvc@16.4.2` convive con `next@15.5.28` | Versiones fijas y `npm ci` reproducible |
| 7.2 | Scripts multiplataforma | Pendiente | `scripts/*.cmd` es solo Windows; puertos 3000/8000 fijos | Scripts Windows/macOS/Linux o documento único; puertos configurables |
| 7.3 | Datos fuera del repositorio | Pendiente | `backend/app/core/config.py:7-8` permite `BANORTE_DB_PATH`, pero el valor por defecto vive en `backend/data` | Base en `%LOCALAPPDATA%`/`$XDG_DATA_HOME` con override; migración de ruta |
| 7.4 | Lanzamiento del MCP empaquetado | Pendiente | `mcp_client.py:36-37` usa `sys.executable`; en un `.exe` se relanzaría el propio ejecutable; `finance_tools.py:18-21` asume el layout del repo | Estrategia explícita para `.exe` (binario/servidor embebido) y prueba de humo |
| 7.5 | Decisión Vercel | Pendiente | `vercel.json:1-20` declara tres servicios; SQLite local y MCP stdio no son durables en un filesystem efímero | O se elimina el despliegue, o se define base gestionada y MCP remoto; probar `vercel` |

---

## Etapa 8 — Documentación y limpieza del repositorio

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 8.1 | Verdad documental | Pendiente | README:44/155 dice 19 herramientas y el servidor registra 20 (`server.py:44-66`); DOMAIN:3 dice "nada aplicado" y hay centavos/migraciones/triggers; REPORTE-QA:3 dice 152 pruebas y hay 302 | Cada cifra y estado coincide con una comprobación |
| 8.2 | Retirar artefactos | Pendiente | Están versionados 27 artefactos del producto (probes, `_d1*.txt`, `tsconfig.tsbuildinfo`, 18 capturas) y 4 archivos de `.archify`; además, 203 archivos del skill vendido bajo `.github/skills/archify` | Repositorio de producto sin artefactos de depuración ni vendor innecesario |
| 8.3 | Corregir `.gitignore` | Pendiente | Las líneas 29-31 están corruptas (`. v e n v /` con caracteres UTF-16) | Ignora `.venv/`, bases y respaldos de forma legible |
| 8.4 | Escaneo final de secretos y PII | Pendiente | `.env` no está versionado y no se hallaron claves; sí hay rutas personales y un nombre de persona en la base | Escaneo de árbol e historia; sin secretos ni PII en el entregable |

---

## Etapa 9 — Entrega, aceptación y operación

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 9.1 | Checklist de aceptación | Pendiente | Ver "Aceptación global" | Checklist firmado con comandos y salidas |
| 9.2 | Prueba en máquina limpia | Pendiente | `scripts/setup.cmd` no se probó desde cero en otra máquina | Instalación, arranque, demo y apagado sin pasos manuales |
| 9.3 | Respaldo y restauración | Parcial | El respaldo se restauró en copia, se migró (`ledger-v1/v2`) con integridad `ok` y la app respondió 200 en health/dashboard/goals; la fila 967 reprodujo el intercambio y falta probar rollback completo | Restaurar un respaldo, migrarlo, verificar integridad/datos con la app y documentar el rollback |
| 9.4 | Salud observable | Pendiente | `/api/health` devuelve `size_bytes: null` por `DB_PATH` no importado (`routes.py:117`) | Tamaño, esquema, herramientas MCP y versión visibles y probados |
| 9.5 | Operación y rollback | Pendiente | No hay runbook | Runbook de respaldo, migración, rollback y soporte |

---

## Aceptación global

1. Base nueva y base real reparada: `reconcile` verde, metas cuadradas con el libro.
2. Se puede completar una meta; al 50% no se marca completada; ningún monto válido devuelve 500.
3. Toda escritura pasa por dominio; REST y MCP tienen paridad; los errores de usuario son 4xx.
4. Reconciliación y salud detectan y reportan los fallos que hoy pasan inadvertidos.
5. Suite backend, pruebas de frontend, typecheck y build en verde; CI reproducible.
6. Sin PII, rutas personales ni secretos en el entregable.
7. Documentación con cifras verificadas y estado real.

---

## Fase A — Corrección de fecha de referencia (2026-11-01)

La compuerta inicial falló con 13 pruebas: la semilla usaba `2026-10-30` y las
herramientas/pruebas usaban `date.today()` (2026-11-01), por lo que noviembre no
tenía datos. Se corrigió la causa raíz, no las pruebas.

| ID | Causa | Corrección | Evidencia |
|---|---|---|---|
| A-1 | Fecha de "hoy" duplicada | `seed.reference_today()` como fuente única; alias interno `finance._today()` | `backend/app/core/seed.py:251`; `backend/app/services/finance.py:22` |
| A-2 | Reglas de fecha con reloj real | `domain.py` y `reconcile.py` usan la referencia | `domain.py:135,149`; `reconcile.py:253` |
| A-3 | Herramientas MCP con reloj real | `finance_tools.py` usa la referencia | `finance_tools.py:74,90,96,187` |
| A-4 | Agente con reloj real | `composer.py` y `orchestrator.py` usan la referencia | `composer.py:280,285`; `orchestrator.py:301,326,333,583,815,1025,1666,1769,1853` |
| A-5 | Aperturas de reparación fechadas con reloj real | `ledger_repair.py` fecha el asiento con la referencia; el sello de auditoría sigue con reloj real | `ledger_repair.py:358` |
| A-6 | Pruebas dependientes del día de ejecución | Pruebas derivan de `reference_today()`; sin literales | `test_bugfixes.py:16`; `test_services.py:5`; `test_purchase_plan.py:8`; `test_savings_contribution.py:4` |
| A-7 | Propagación incompleta | `start-all.cmd` propaga `BANORTE_DEMO_TODAY`; README lo documenta | `scripts/start-all.cmd:9-17,42,61`; `README.md:94-97` |
| A-8 | Reloj real encubierto en las rutas REST | `routes.py` usa `seed.reference_today()` en la fecha límite, el mes por defecto y la respuesta de presupuesto; pruebas nuevas | `backend/app/api/routes.py:11,82,90,288`; `backend/tests/test_services.py:80-96` |

**Puerta de salida de Fase A (verificada 2026-11-04):**
`reconcile(conn)` con referencia por defecto (`2026-10-30`) → `ok=true`,
`failures=0`, 13 invariantes; `npm run build` (frontend) → exit 0;
`grep date.today()` (incluye alias `date_cls.today()` y `datetime.today()`)
en `backend` y `mcp-server` → 0 coincidencias; `xfail`/`skip` en
`test_agent_grounding.py` → 0. Suite: `384 passed`. `AGENTS.md` y
`.github/copilot-instructions.md` presentes.

**Bloqueo de datos resuelto:** las transacciones 968 y 969 de
`backend/data/banorte.db` están normalizadas a `2026-10-20`. No se halló el
respaldo previo a la normalización (ni en `backend/data/backups` ni en el
historial de git), por lo que se registró un respaldo verificado del estado ya
normalizado: `backend/data/backups/banorte.db.bak-20261104-184225` con SHA-256
`b4bb7220f95e7487ccaf9465f78f5f5c6e42da7891e408a6e59fb0a7277f8366`, idéntico
al de la base. Comprobación: filas 968/969 con fecha `2026-10-20`;
`PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = `[]`;
reconciliación `ok=true`, `failures=0`, 13 invariantes. Auditoría completa en
`docs/AUDITORIA-NORMALIZACION-968-969.json`.

**Guardrail de escritura (código, no solo documentación):**
`migrate.require_verified_backup(conn, motivo)` exige, antes de cualquier
transacción, que el respaldo exista, no esté vacío, coincida con su SHA-256
declarado, pase `PRAGMA integrity_check`, no tenga referencias foráneas rotas y
sea idéntico al estado actual de la base; si falla, lanza `MigrationError` y no
se escribe nada (`migrate.py:164`). Se invoca en `migrate.run_pending` (antes
de crear el registro de versiones o aplicar migraciones, `migrate.py:664-671`)
y en `ledger_repair.run` (antes de `BEGIN IMMEDIATE`, `ledger_repair.py:347`).
Pruebas sobre bases
temporales: `test_migration_cents.py::test_run_pending_aborts_without_verified_backup`,
`test_ledger_repair.py::test_guard_aborts_without_backup`,
`test_guard_accepts_verified_backup`, `test_guard_rejects_tampered_backup` y
`test_apply_aborts_when_backup_creation_fails`.

## Fase A — Catálogo MCP y contratos (2026-11-02)

| ID | Tarea | Estado | Evidencia |
|---|---|---|---|
| MCP-1 | Catálogo único de las 20 herramientas | **Hecho** | `backend/app/services/mcp_catalog.py` define nombre, descripción, modelo de entrada, riesgo, permisos, auditoría, confirmación, idempotencia y contrato de salida |
| MCP-2 | Validación estricta de argumentos | **Hecho** | Modelos Pydantic con `extra="forbid"`, límites, enums, fechas, UUID y nombres; `validate_arguments()` y `validated_tool()` |
| MCP-3 | Servidor MCP guiado por catálogo | **Hecho** | `mcp-server/server.py` registra implementaciones desde `CATALOG`, publica el esquema estricto y rechaza campos desconocidos antes de ejecutar |
| MCP-4 | Sin listas paralelas en el agente | **Hecho** | `orchestrator.py` importa `MCP_ALLOWED_TOOLS` y `WRITE_TOOLS` del catálogo |
| MCP-5 | Guardia de descubrimiento | **Hecho** | `mcp_client.start()` exige que las herramientas descubiertas coincidan exactamente con el catálogo |
| MCP-6 | Auditoría de riesgo y confirmación | **Hecho** | `_call_mcp_tool()` y `execute_pending()` registran `tool_risk`, `requires_confirmation`, `idempotency` e `idempotent_replay`; allowlist en `structured_logging.py` |
| MCP-7 | Pruebas del catálogo y protocolo | **Hecho** | `backend/tests/test_mcp_catalog.py` y `test_mcp_tools.py`; suite `328 passed in 158.05s` |
| MCP-8 | `sin_dato` tipado en respuestas vacías | **Hecho** | `add_sin_dato()` en `mcp_catalog.py`; 14 herramientas con `returns_no_data=True` devuelven `{"sin_dato": {"code", "message", "period"}}`; prueba de vacío en `test_mcp_tools.py` |

**Pendiente explícito (no cerrado en esta fase):** paridad REST/MCP completa de
saneamiento y errores 4xx, y pruebas de concurrencia de confirmaciones
(Etapas 3 y 6).

## Fase B — Sesiones, prompt y costo del agente (2026-11-03)

| ID | Requisito | Estado | Evidencia |
|---|---|---|---|
| B-1 | Aislamiento por `session_id` | **Hecho** | `ChatRequest.session_id` genera UUID si falta (`schemas/api.py:117-120`); `chatStore.ts:25,46-60` conserva un id por conversación y `AgentView.tsx:65-66` lo envía junto con los últimos 6 turnos. `session_store.py:12-15,18-32,37-55` mantiene estado separado por sesión, TTL de 30 minutos y máximo 200; `test_agent_session_prompt_cost.py:32-72` comprueba aislamiento, expiración y descarte de la sesión más antigua. |
| B-2 | Prompt externo, validado y versionado | **Hecho** | `system_prompt.md:1` declara `1.0.0`; `prompt_loader.py:10-22,36-72` valida versión y secciones; `orchestrator.py:47-49` lo carga al importar el backend, por lo que un archivo ausente o inválido impide iniciar con `PromptError`. `orchestrator.py:2413-2422` registra `prompt_version` en la traza; pruebas en `test_agent_session_prompt_cost.py:75-109`. |
| B-3 | Uso de tokens y tope de costo con respaldo | **Hecho** | `providers.py:29-38` expone tokens de entrada/salida; `config.py:25-60,95-96` define tope predeterminado de USD 0.05 y precios configurables por modelo. `orchestrator.py:2189-2206` acumula costo, detiene el bucle y registra el exceso o la falta de `usage`; `orchestrator.py:2458-2465` registra el respaldo local. Prueba simulada y de falta de `usage` en `test_agent_session_prompt_cost.py:112`. |
| B-4 | Orden de alertas y nombre declarado de meta | **Hecho / verificado** | `orchestrator.py:417-420` prioriza referencias a metas ante palabras de alerta; `test_agent_session_prompt_cost.py:189,196` prueba detección y resolución de «Fondo de emergencia». `test_agent_session_prompt_cost.py:220` prueba que no se crea una meta sin nombre y que el nombre declarado queda pendiente; `test_savings_contribution.py:178-234` verifica confirmación y replay idempotente. |

**Puerta de salida Fase B:** `339 passed` con
`..\.venv\Scripts\python.exe -m pytest tests -q --basetemp $pytestBase`;
`npm run build` en `frontend` terminó con exit 0. Para repetir en PowerShell:

```powershell
Set-Location backend
$pytestBase = Join-Path $env:TEMP ("banorte-fase-b-" + [guid]::NewGuid().ToString())
..\.venv\Scripts\python.exe -m pytest tests -q --basetemp $pytestBase
Set-Location ..\frontend
npm run build
```

**Re-verificación de cierre (2026-11-03):** no había lógica pendiente de Fase B;
no se reescribió código. Se confirmó por lectura y ejecución:

| ID | Requisito | Estado | Evidencia de la re-verificación |
|---|---|---|---|
| B-1 | Aislamiento por sesión | Verificado | `session_store.py:12-15` define TTL 30 min y máximo 200; `session_store.py:37-47` expira y descarta la sesión más antigua; `session_store.py:18-33` contiene todas las claves de sesión; `schemas/api.py:117-120` genera `session_id`; `AgentView.tsx:65,181` lo envía en chat y confirmación. `test_agent_session_prompt_cost.py:32-72` cubre aislamiento, TTL y descarte. |
| B-2 | Prompt en archivo propio | Verificado | `system_prompt.md:1` declara `1.0.0`; `prompt_loader.py:10-22,36-65` exige versión y secciones; `orchestrator.py:47-50` carga al importar; `orchestrator.py:2418-2426` registra `prompt_version`; `test_agent_session_prompt_cost.py:75-109` prueba archivo ausente/malformado y versión en traza. |
| B-3 | Límite de costo | Verificado | `providers.py:29-38` expone `prompt_tokens`/`completion_tokens`; `config.py:25-60,95-96` define `AGENT_MAX_COST_USD=0.05` y precios por modelo; `orchestrator.py:2187-2206` acumula y corta; `orchestrator.py:2281-2293` estima; `test_agent_session_prompt_cost.py:112-186` prueba corte con respaldo y ausencia de `usage`. |
| B-4 | Orden de resolución | Verificado | `orchestrator.py:417-420` resuelve referencias a metas antes de alertas; `test_agent_session_prompt_cost.py:189-217` prueba «Fondo de emergencia»; `test_agent_session_prompt_cost.py:220-237` prueba que sin nombre no hay acción y con nombre declarado queda pendiente de confirmación. |

Resultado de la puerta: `339 passed in 86.22s`; `npm run build` exit 0; sin
`xfail` ni `skip` en `backend/tests`.

## Fase C — Fundamentación, `sin_dato` y minimización (2026-11-03)

| ID | Requisito | Estado | Evidencia |
|---|---|---|---|
| C-1 | Verificador de fundamentación | **Hecho** | `ground_check()` extrae cifras del texto y las contrasta con todos los números de `tool_results`, incluidas diferencias y porcentajes calculados con `money.py` (`orchestrator.py:262-280`). Si falla, `_request_grounding_retry()` pide una sola corrección (`orchestrator.py:2556-2589`); si persiste, `_grounding_fallback()` sustituye el texto (`orchestrator.py:312-319`). La traza registra `grounding_extracted`, `grounding_unsupported` y `grounding_blocked` (`orchestrator.py:2501-2533`). |
| C-2 | `sin_dato` explícito, sin ceros inventados | **Hecho** | `_correct_sin_dato()` detecta `sin_dato` en cualquier resultado anidado y sustituye ceros o respuestas vacías por el mensaje tipado de la herramienta (`orchestrator.py:303-309`). Un cero real sin `sin_dato` sigue permitido. Pruebas de cero con y sin `sin_dato` en `test_agent_grounding.py:111-164`. |
| C-3 | Minimización antes del proveedor | **Hecho** | `_mask_tool_result()` copia el resultado y redacta claves sensibles (`name`, `customer`, `email`, `phone`, `card`, `account`, `token`, etc.) y cadenas con NIP, correo o números largos (`orchestrator.py:322-336`); se aplica justo antes de `tool_result_message` (`orchestrator.py:2447`). El resultado completo se conserva para la UI y la fundamentación. Prueba de fuga en `test_agent_grounding.py:167-185`. |
| C-4 | Registros sin PII | **Hecho** | `mask_pii()` redacta correos, teléfonos, números largos y etiquetas sensibles (`structured_logging.py:39-47`); el formateador lo aplica a los campos permitidos (`structured_logging.py:68-71`). Prueba en `test_observability.py:51-70`. |
| C-5 | Cobertura de desarrollo y retención | **Hecho** | `GROUNDING_CASES` contiene 10 casos; 4 son retención (40 %, por encima del 30 % exigido): `test_agent_grounding.py:188-239`. Resultado: 10/10 en total y 4/4 en retención. |

**Puerta de salida Fase C:** `358 passed in 154.13s` con
`..\.venv\Scripts\python.exe -m pytest tests -q --basetemp $pytestBase`;
`npm run build` en `frontend` terminó con exit 0; reconciliación
`{"ok": true, "failures": 0, "invariant_count": 13, "failed": []}`.

**Cierre 4.3 (2026-11-03):** se sanearon los 11 archivos versionados con
rutas personales y se regeneró la base local desde la semilla sintética. La
guardia `test_no_pii.py:41-77` revisa los archivos versionados y las bases
locales; el scan manual terminó en `PII_SCAN_CLEAN`. Evidencia:

- `pytest tests/test_no_pii.py -q --basetemp <temp>` → `2 passed in 8.97s`.
- Base regenerada: metas `Fondo de emergencia`, `Viaje a Japón` y `Enganche
  del auto`; `pii_name_count=0`; respaldos locales eliminados.
- Puerta 4.3: `360 passed in 258.02s`; `npm run build` en `frontend` con exit
  0; reconciliación `{"ok": true, "invariant_count": 13, "failures": 0}`.

**Cierre 4.4 (2026-11-03):** las confirmaciones dejaron de vivir en memoria y
ahora se persisten en SQLite con token opaco (solo se guarda su SHA-256), TTL de
30 minutos, vínculo a sesión/principal/trace, consumo atómico con
`BEGIN IMMEDIATE`, replay del resultado y liberación si la herramienta falla.
La migración `confirm-v1` crea `pending_confirmations`; el guardián de esquema la
exige al arrancar. Evidencia:

- `pytest tests/test_confirmations.py ... tests/test_bugfixes.py -q --basetemp
  <temp>` → `236 passed in 171.45s`.
- Puerta 4.4: `369 passed in 229.96s`; `npm run build` en `frontend` con exit 0;
  reconciliación `{"ok": true, "invariant_count": 13, "failures": 0}`.
- Base local migrada a `confirm-v1` con `pending_confirmations` presente,
  `pii_name_count=0` y respaldos locales eliminados.
- `git grep` de rutas personales → `PII_SCAN_CLEAN`; `git diff --check` →
  `DIFF_CHECK_OK`.
- Se corrigió `current_version` para ordenar por `rowid DESC` (`migrate.py:90`,
  `routes.py:88`), de modo que la versión vigente no dependa del orden
  lexicográfico de los nombres.

**Cierre 4.5 (2026-11-03):** la API quedó protegida por sesión de administrador
con cookie `HttpOnly` firmada, hash PBKDF2 en entorno, sesiones persistentes y
CSRF de doble envío. `BANORTE_PUBLIC=1` sin auth o sin cookie `Secure` impide
arrancar; el modo local queda explícitamente sin auth. Evidencia:

- `pytest tests/test_auth.py -q --basetemp <temp>` → `5 passed in 6.11s`.
- Puerta 4.5: `374 passed in 84.38s`; `npm test` → `9 passed`; `npm run build`
  en `frontend` con exit 0; reconciliación `{"ok": true, "invariant_count": 13,
  "failures": 0}`.
- Base local migrada a `auth-v1` con `auth_sessions` presente y respaldos
  eliminados; `PII_SCAN_CLEAN`; `DIFF_CHECK_OK`; `NO_XFAIL_OR_SKIP`.
- Se corrigió el orden de middleware para que CORS aplique también a 401/403
  (`main.py:62-90`) y `ensure_database` revalida la versión antes de saltar la
  migración (`database.py:62-68`).

**Cierre 4.6 (2026-11-03):** la suite de inyección usa un proveedor falso que
recibe datos maliciosos en `category`/`description` y simula que el modelo
intenta escribir o llamar una herramienta fuera de la lista. El orquestador
fuerza `confirm=False`, registra una confirmación pendiente y rechaza la
herramienta no permitida antes de tocar MCP. Evidencia:

- `pytest tests/test_agent_injection.py -q --basetemp <temp>` → `7 passed in
  2.65s`.
- `pytest tests/test_agent_injection.py
  tests/test_bugfixes.py::TestBug004PromptInjection tests/test_confirmations.py
  -q --basetemp <temp>` → `58 passed in 15.25s`.
- Puerta 4.6: `381 passed in 87.62s`; `npm test` → `9 passed`; `npm run build`
  en `frontend` con exit 0; reconciliación `{"ok": true, "invariant_count": 13,
  "failures": 0}`; `PII_SCAN_CLEAN`; `DIFF_CHECK_OK`; `NO_XFAIL_OR_SKIP`.
- Se sustituyó la aserción vacua `or True` por comprobaciones del texto visible
  y de los parámetros pendientes (`test_bugfixes.py:210-218`).
- La UI y el eco del modelo se sanean con `_sanitize_injected_text` /
  `_has_output_injection` (`orchestrator.py:595-617,2350-2377,2561-2566`); la
  prueba de ruta confirma que solo `/agent/confirm` ejecuta el token y que el
  replay no repite la escritura (`test_agent_injection.py:262-303`).

**Re-verificación de puerta (2026-11-04):** el inventario de Fase A detectó un
reloj real encubierto: `routes.py` usaba `date_cls.today()` en la validación de
`deadline`, en el mes por defecto de dashboard/presupuesto y en la respuesta de
`budget/update`. Se sustituyó por `seed.reference_today()` (`routes.py:11,82,90,288`)
y se añadieron dos pruebas que fallaban antes del cambio
(`test_services.py:80-96`). En 4.6 se detectó que la confirmación pendiente
exponía `params` sin sanear; ahora se aplica `_sanitize_injected_text()` a los
`params` (`orchestrator.py:2461`) y la prueba nueva
`test_agent_injection.py:134-164` fallaba antes y pasa después.

Evidencia de la puerta re-ejecutada:

- `pytest tests/test_no_pii.py -q` → `2 passed`; `git grep` de rutas/PII →
  `PII_SCAN_CLEAN`.
- `pytest tests/test_confirmations.py -q` → `9 passed`.
- `pytest tests/test_auth.py -q` → `5 passed`.
- `pytest tests/test_agent_injection.py -q` → `8 passed`.
- Suite completa: `384 passed in 253.59s`; `npm test` → `9 passed`.
- `npm run build` en `frontend` → exit 0; reconciliación
  `{"ok": true, "failures": 0, "invariant_count": 13}`.
- `date.today()`/`date_cls.today()`/`datetime.today()` en `backend` y
  `mcp-server` → 0; `xfail`/`skip` en `test_agent_grounding.py` → 0;
  `git diff --check` → `DIFF_CHECK_OK`.

**Alcance:** esta fase cierra 4.1, 4.2, 4.3, 4.4, 4.5 y 4.6. Etapa 4 completa.

## Punto de continuación

**Fase A y Etapa 4 cerradas (2026-11-04).** La base real reconcilia `ok=true`,
`failures=0`; el respaldo de la normalización 968/969 está verificado
(`backend/data/backups/banorte.db.bak-20261104-184225`, SHA-256
`b4bb7220…f8366`). Ver `docs/AUDITORIA-NORMALIZACION-968-969.json`.

**Etapa 2.5 ejecutada (2026-11-04).** `ledger-v3` se aplicó a
`backend/data/banorte.db` con respaldo verificado y transacción única. La base
ya era consistente: no hubo filas que reparar (`ids_afectados=[]`), el SHA-256
quedó sin cambios (`b4bb7220…f8366`) y `reconcile` antes/después dio
`ok=true`, `failures=0`, 13 invariantes. Respaldo:
`backend/data/backups/banorte.db.bak-20261104-221035`; auditoría:
`docs/AUDITORIA-LEDGER-V3-20261104-221035.json`.

**Puerta re-ejecutada tras 2.5 (2026-11-04):** `pytest -q backend` →
`389 passed`; `npm test` → `9 passed`; `npm run build` → exit 0; reconciliación
`{"ok": true, "failures": 0, "invariant_count": 13}`; sin coincidencias de
`date.today()`/`date_cls.today()`/`datetime.today()` en `backend` y
`mcp-server`; sin `xfail`/`skip` en `backend/tests`; `git diff --check` →
`DIFF_CHECK_OK`; filas 968/969 con fecha `2026-10-20`.

**Siguiente etapa:** Etapa 3 (validación única y paridad REST/MCP), todavía
pendiente en 3.1–3.8. No avanzar a Etapa 5 hasta cerrar 3.

---

## Decisiones de la Etapa 2

1. **Reparar, no resembrar** (resuelto): `ledger-v3` corrige 967, rellena piernas y crea aperturas explícitas 968/969. La base real quedó reparada y verificada.
2. **Ahorro inicial = apertura explícita** (resuelto): no se inventan transferencias en silencio; cada apertura se reporta como movimiento propio y requiere `--accept-openings`.
3. **Piernas de transferencia** (resuelto): se acepta `transfer_legs` para reconstruir cada cuenta debitada.
4. ¿El producto se entrega solo local o se publica? De esto dependen autenticación y la decisión sobre Vercel. **Pendiente.**
