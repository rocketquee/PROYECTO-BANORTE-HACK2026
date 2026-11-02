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
| 2 | Reparación y reconciliación del libro | **2.1–2.8 cerradas en copia; 2.5 real pendiente de aprobación** | 1 | `backend/app/core/ledger_repair.py` |
| 3 | Validación única y paridad REST/MCP | **Pendiente** | 2 | `backend/app/services/domain.py`, `routes.py` |
| 4 | IA: fundamentación, privacidad y confirmaciones | **Pendiente** | 2, 3 | `backend/app/services/agent/orchestrator.py` |
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
| 2.5 | Reparar la base real con migración versionada | **Hecho en copia; base real pendiente de aprobación** | `backend/app/core/ledger_repair.py` (plan/apply, `BEGIN IMMEDIATE`, respaldo + SHA-256, auditoría); `tests/test_ledger_repair.py` (4 pruebas). Copia reparada: fila 967 → cuenta 2/meta 3, 1 pierna, aperturas 968/969, `reconcile` verde, `failures=0`. Base real intacta: SHA-256 `48AED474…C287BB`, 237,568 bytes | Corregir el `INSERT` de `ledger-v1` y su verificación por fila; migración `ledger-v3` con respaldo verificado deja los tres saldos y el movimiento 967 consistentes; `reconcile` verde |
| 2.6 | Corregir el fondeo de la semilla | **Hecho** | `seed.py` inserta metas con `saved=0` y las fondea con `finance.apply_transfer`; `tests/test_transfer_accounting.py` verifica que toda meta con ahorro tiene libro y que dos siembras dan el mismo SHA-256 | Toda meta sembrada con ahorro > 0 tiene su transferencia; base nueva reconcilia al 100% |
| 2.7 | Registrar todas las cuentas debitadas | **Hecho** | `TRANSFER_LEGS_DDL` + `transfer_legs`; `_debit_accounts_cents` devuelve todas las piernas y `apply_transfer` las inserta; `tests/test_transfer_accounting.py` cubre multi-cuenta y reconstrucción por cuenta | Una transferencia multi-cuenta conserva todas las piernas y permite reconstruir cada saldo |
| 2.8 | Congelar el calendario de la semilla | **Hecho** | `DEFAULT_REFERENCE_DATE = 2026-10-30`; `BANORTE_DEMO_TODAY` lo sobrescribe; `tests/test_transfer_accounting.py` compara SHA-256 de dos siembras | Semilla reproducible con fecha fija por defecto o documentada como variable obligatoria |
| 2.9 | Fecha de referencia única en datos, herramientas y pruebas | **Hecho** | `seed.py:251` expone `reference_today()`; la usan `finance._today()`, `domain.py:135,149`, `reconcile.py:253`, `ledger_repair.py:358`, MCP (`finance_tools.py:74,90,96,187`), `composer.py:280,285`, `orchestrator.py` y las pruebas. `grep date.today()` en `backend` y `mcp-server` → 0 | Semilla, backend, MCP y pruebas comparten el mismo "hoy"; sin `date.today()` ni fechas literales; suite 319 en verde |

**Aceptación de Etapa 2**

1. Base nueva: completar una meta funciona; al 50% sigue activa; `reconcile` verde.
2. Base real reparada (**pendiente de aprobación**): metas 1–4 cuadran con el libro; movimiento 967 apunta a la meta correcta. La copia ya cumple.
3. Aportación multi-cuenta reconstruible por cuenta.
4. Suite backend (317) y build de frontend en verde, con pruebas nuevas de borde.

**Archivos principales:** `backend/app/services/finance.py`, `backend/app/core/seed.py`, `backend/app/core/reconcile.py`, `backend/app/core/migrate.py`, `backend/tests/test_savings_contribution.py`.

---

## Etapa 3 — Validación única y paridad REST/MCP

**Objetivo:** una sola autoridad de validación; los dos transportes aceptan y rechazan exactamente lo mismo; ningún dato inválido entra por PATCH ni por MCP.

| ID | Tarea | Estado | Evidencia / archivo | Criterio de cierre |
|---|---|---|---|---|
| 3.1 | Validar `status` con dominio cerrado | Pendiente | `schemas/api.py:34` lo declara `str`; `finance.py:466-467` lo escribe sin validar; prueba: `PATCH {"status":"banana"}` devuelve 200 | `status` es `Literal` y la base tiene CHECK; valor inválido devuelve 422 |
| 3.2 | Validar fecha límite en PATCH y MCP | Pendiente | `finance.py:464-465` asigna la fecha sin parsear; `PATCH {"deadline":"2000-01-01"}` devuelve 200; MCP no valida `deadline` (`finance_tools.py:196-245`) | Fecha inválida o pasada devuelve 422 en REST y error de herramienta en MCP |
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
| 4.1 | Verificador de fundamentación | Pendiente | `live_response` usa el texto del proveedor sin contrastarlo con `tool_results` (`orchestrator.py:2092-2208`) | Toda cifra del texto debe existir en una herramienta; si no, se sustituye por respuesta determinista |
| 4.2 | Minimización de datos antes del proveedor | Pendiente | `live_response` envía resultados de `get_savings_goals` al proveedor; la base real contiene una meta con nombre de persona | Los nombres y datos no necesarios se redactan antes de salir; prueba de fuga |
| 4.3 | Inventario y limpieza de PII | Pendiente | Meta 4 creada 2026-10-25; 9 archivos versionados contienen rutas personales de Windows | Base de entrega sin PII; repositorio sin rutas personales; política documentada |
| 4.4 | Confirmaciones con vigencia y alcance | Pendiente | `_PENDING` es global y sin expiración (`orchestrator.py:2278-2304`); el token de compra vive en memoria del proceso | Token de un solo uso, TTL, ligado a sesión/trace y probado contra replay |
| 4.5 | Autenticación si se publica | Pendiente | No hay `Depends`/`Security` en `routes.py`; escrituras y `/agent/confirm` quedan abiertas | Si hay despliegue público: autenticación, autorización y CSRF; si es local, declararlo y bloquear el despliegue |
| 4.6 | Inyección de prompt con datos | Pendiente | Resultados de herramientas se envían como mensajes al modelo; las guardas actuales son regex de entrada | Suite de inyección con descripciones/categorías maliciosas; el modelo no gana herramientas ni escrituras |

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

**Puerta de salida de Fase A:** `319 passed`; `npm run build` exit 0;
`grep date.today()` → 0; `AGENTS.md` y `.github/copilot-instructions.md`
presentes.

**Bloqueo de datos pendiente de aprobación:** con la referencia canónica
(`2026-10-30`) la reconciliación de `backend/data/banorte.db` marca INV-6 por
las aperturas 968 y 969, fechadas `2026-11-01` por una reparación anterior que
usó el reloj real. Con `BANORTE_DEMO_TODAY=2026-11-01` la reconciliación da
`ok=true`, `failures=0`, pero la suite falla porque la semilla de ese día solo
genera un día de datos. Normalizar esas dos filas a la fecha de referencia
exige respaldo, transacción y auditoría (aprobación explícita). El inventario de
herramientas MCP queda pendiente de aprobación.

## Punto de continuación

**Etapa 2 cerrada en copia.** Falta una sola autorización: aplicar `ledger-v3` a `backend/data/banorte.db`.

Comando previsto (con la app detenida; el script se niega a correr sobre la base real sin `--apply` explícito y guarda respaldo + SHA-256):

```
cd backend
..\.venv\Scripts\python.exe -m app.core.ledger_repair --apply --accept-openings
```

Después de aplicarlo: repetir `reconcile` sobre la base real, verificar el SHA-256 del respaldo y conservar el JSON de auditoría.

**Siguiente tarea tras la aprobación:** Fase A / Etapa 3 (herramientas propias + capa de dominio). No iniciar la Etapa 3 hasta que la base real esté reparada o el usuario decida explícitamente posponerlo.

---

## Decisiones de la Etapa 2

1. **Reparar, no resembrar** (resuelto para la copia): `ledger-v3` corrige 967, rellena piernas y crea aperturas explícitas 968/969. La base real espera aprobación.
2. **Ahorro inicial = apertura explícita** (resuelto): no se inventan transferencias en silencio; cada apertura se reporta como movimiento propio y requiere `--accept-openings`.
3. **Piernas de transferencia** (resuelto): se acepta `transfer_legs` para reconstruir cada cuenta debitada.
4. ¿El producto se entrega solo local o se publica? De esto dependen autenticación y la decisión sobre Vercel. **Pendiente.**
