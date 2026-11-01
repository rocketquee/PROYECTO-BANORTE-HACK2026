# ESTADO DEL PROYECTO — Auditoría técnica independiente

**Repositorio:** `proyecto-banorte-ai-finanzas`
**Rama / commit:** `main` / `7062c60`
**Fecha de auditoría:** 2026-10-30
**Actualización:** 2026-10-30 — Etapa 2.1/2.2 aplicada en `finance.py` con 7 pruebas nuevas; la base real sigue intacta.
**Alcance:** lectura completa, ejecución de pruebas, build, arranque con base temporal, consultas sobre copia de la base real y corrección del flujo de aportaciones.
**Regla aplicada:** ninguna afirmación sin archivo:línea o salida de comando. La base real no se usó para escrituras.

---

## 1. Veredicto en cinco líneas

1. El proyecto es un prototipo funcional y demostrable: contrato UI validado, servidor MCP real con 20 herramientas, dinero en centavos, migraciones versionadas y una suite de 302 pruebas que pasa.
2. El flujo de aportaciones ya funciona tras 2.1: el 50% deja la meta activa, el 100% la completa y el retiro la reabre; siguen abiertos el desajuste libro-metas (R-2), la semilla de metas 1–2 (2.6) y el débito multi-cuenta (R-3).
3. La reconciliación propia devuelve `ok: true` pese a diferencias entre ahorro y transferencias de $18,500, -$14,300 y $22,500, por lo que la señal de integridad no es confiable.
4. La documentación está desactualizada y se contradice con el código en número de herramientas MCP, pruebas, estado de las migraciones y volumen de datos.
5. Veredicto: **apto para demostración local controlada; no apto para entrega como producto, custodia de datos ni despliegue público** hasta cerrar las Etapas 2 y 3 de `docs/PLAN.md`.

---

## 2. Tabla maestra: Área | Elemento | Estado | Evidencia

| Área | Elemento | Estado | Evidencia |
|---|---|---|---|
| A. Reto | Servidor MCP y herramientas | **Hecho, con discrepancia documental** | `mcp-server/server.py:44-66` registra 20 herramientas; el arranque reporta `service_count: 20`; README:44/155 dice 19 |
| A. Reto | Contrato UI autorizado | **Hecho** | 14 componentes en `backend/app/schemas/ui.py:336-341` y `frontend/src/types/contract.ts:260-275`; Pydantic `extra="forbid"` |
| A. Reto | Renderer fijo, sin código ejecutable | **Hecho** | `DynamicRenderer.tsx:44-126` mapea solo tipos autorizados; no hay `dangerouslySetInnerHTML` ni `eval` en `frontend/src` |
| A. Reto | Validación del contrato en el cliente | **Parcial** | `chatStore.ts:97-105` hace `JSON.parse` y cast; el renderer solo comprueba `type` |
| A. Reto | Ciclo cerrado universal | **Parcial** | Solo compra y aportación envían `ui_event` (`AgentView.tsx:53-66, 92-162`); otras tarjetas solo pueden enviar una pregunta de texto (`SpendingChart.tsx:71`, `CreditSimulator.tsx:115`), no un evento de acción; filtros y toggles no vuelven; README:20 generaliza |
| B. Datos | Esquema real | **Hecho** | 7 tablas, sin vistas; `transactions` con `type` y `direction`; `PRAGMA integrity_check` = `ok`; `foreign_key_check` sin filas |
| B. Datos | Dinero en centavos | **Hecho** | Columnas `*_cents INTEGER`; migración `ledger-v2` aplicada; `schema_migrations.result_json` confirma conversión de 5 tablas |
| B. Datos | Migraciones y respaldo | **Hecho** | `ledger-v1` y `ledger-v2` aplicadas 2026-10-30 00:52:54; respaldo `banorte.db.bak-20261029-185254` con SHA-256 coincidente |
| B. Datos | Semilla de metas | **Parcial** | Metas 1 y 2 se insertan con ahorro directo sin transferencia (`seed.py:202-209, 338-344, 348-353`); meta 3 ya no nace `completada` al 50% tras 2.1 |
| B. Datos | Aportación que completa una meta | **Hecho** | 2.1: meta de $1,000 + dos abonos de $500 -> 200 y `status: completada`; `tests/test_transfer_accounting.py`; `finance.py:529-561` |
| B. Datos | Aportación del 50% | **Hecho** | 2.1: meta de $1,000 + abono de $500 -> 200, `saved_amount: 500`, `status: activa`; también 51% y 60% (`tests/test_transfer_accounting.py`) |
| B. Datos | Retiro de una meta completada | **Hecho** | 2.1: retiro de $100 sobre una meta de $1,000 -> 200, 90%, `status: activa`; `tests/test_transfer_accounting.py` |
| B. Datos | Débito multi-cuenta | **Parcial / fallido** | `finance.py:478-502` debita varias cuentas; `finance.py:550-555` guarda un solo `account_id`; prueba: abono de $50,000 debita cuentas 2 y 1 y registra solo la 2 |
| B. Datos | Movimiento 967 y meta | **Fallido** | `schema_migrations.result_json` de `ledger-v1`: `id 967 -> goal_id 3`; fila real: `goal_id=2`; `migrate.py:310-317` intercambia los parámetros de `account_id` y `goal_id`; meta 2 libro $22,500 vs ahorro $8,200; meta 3 ahorro $22,500 vs libro $0 |
| B. Datos | Reconciliación de invariantes | **Fallido** | `reconcile.py:57-70` solo valida cotas; `reconcile.py:123-156` devuelve `ok: true` sobre la base real con las tres diferencias anteriores |
| B. Datos | Idempotencia de aportaciones | **Hecho** | Repetición de la misma clave devuelve `idempotent_replay: true` y no duplica; `savings.py:88-112`; registros reales en `idempotency_records` |
| C. IA | Modo demo | **Hecho** | Sin clave, `provider_mode()` = `demo`; `demo_response` usa reglas y MCP real; arranque y chat verificados con base temporal |
| C. IA | Modo en vivo | **Parcial** | OpenAI/Anthropic implementados (`providers.py:35-141`); no se probó con claves reales; el texto final del modelo no se contrasta con herramientas |
| C. IA | Verificador de fundamentación | **Pendiente** | `live_response` devuelve `final_text` sin validar cifras (`orchestrator.py:2092-2208`) |
| C. IA | Privacidad / PII | **Fallido** | Base real con una meta de nombre de persona (id 4, 2026-10-25); 9 archivos versionados con rutas absolutas de Windows; README:5 afirma "datos 100% sintéticos" |
| D. Validación | PATCH de metas | **Fallido** | `PATCH {"status":"banana"}` -> 200; `PATCH {"deadline":"2000-01-01"}` -> 200; `PATCH {"name":"<script>alert(1)</script>"}` -> 200; `schemas/api.py:33-34`, `finance.py:464-467` |
| D. Validación | Presupuesto en cero | **Fallido** | `POST /api/budget/update {"monthly_limit":0}` -> 500; esquema acepta `ge=0` (`api.py:48`) y la tabla exige `> 0` (`seed.py:96-101`) |
| D. Validación | Paridad REST/MCP | **Parcial** | REST limita a $10,000,000 (`routes.py:58-62`); MCP a $100,000,000 (`finance_tools.py:207`); MCP no valida fecha ni sanea nombre; solo aporta, no retira |
| E. Salud | `/api/health` | **Fallido** | `size_bytes` siempre `null`; `routes.py:117` usa `DB_PATH` sin importarlo y el `except` oculta el `NameError` |
| E. Calidad | Suite backend | **Hecho, con huecos** | 302 pruebas recolectadas y `302 passed in 530.42s`; las 7 nuevas cubren 2.1; aún no cubre reconciliación libro-metas ni concurrencia |
| E. Calidad | Golden contract | **Fallido / deriva** | `tests/golden_contract.py` no está en pytest; reporta 18 diferencias: fecha real vs `DEMO_TODAY`, campos de health, redondeo de crédito y estado de meta 3 por 2.1 |
| E. Calidad | Pruebas frontend | **Parcial** | 9 pruebas pasan; `frontend/tests/*.test.mjs` leen archivos y comparan regex, no renderizan componentes ni simulan interacción |
| E. Calidad | Typecheck y build | **Hecho** | `npx tsc --noEmit` exit 0; `npm run build` exit 0 con Next.js 15.5.28 |
| E. Calidad | CI, lint y cobertura | **Fallido** | No hay `.github/workflows`; `frontend/package.json` no tiene script `lint`; no hay ruff/eslint/coverage |
| F. Portabilidad | Dependencias | **Parcial** | `requirements.txt` con `>=`; `package.json` con `^`; `@next/swc-win32-x64-msvc@16.4.2` junto a `next@15.5.28` |
| F. Portabilidad | Scripts y rutas | **Parcial** | `scripts/*.cmd` solo Windows; puertos 3000/8000 fijos; MCP usa `sys.executable` (`mcp_client.py:36-37`) |
| F. Portabilidad | Vercel | **No verificado** | `vercel.json` declara 3 servicios; no se desplegó; SQLite local y MCP stdio no son durables en filesystem efímero |
| G. UX | Accesibilidad real | **No verificado** | No se ejecutó axe/Lighthouse ni prueba con lector de pantalla |
| G. UX | Rendimiento | **No verificado** | 967 movimientos; no hay prueba de carga ni de volumen objetivo |
| H. Docs | Verdad documental | **Fallido** | README:44/155 (19 vs 20 herramientas); REPORTE-QA:3/44 (152 vs 302 pruebas); DOMAIN:3 ("nada aplicado" vs migraciones/centavos/triggers); DATA-DICTIONARY:1568 (~984 vs 967 movimientos) |
| H. Repo | Higiene | **Fallido** | 27 archivos de producto son artefactos de depuración o capturas; `.archify` aporta 4 y `.github/skills/archify` 203 archivos vendidos; `.gitignore` tiene una línea final corrupta |

---

## 3. Discrepancias entre documentos y código

| Documento | Afirmación | Realidad verificada | Severidad |
|---|---|---|---|
| `README.md:44,155`; `docs/ARQUITECTURA.md:28` | 19 herramientas MCP | 20 registradas y descubiertas (`server.py:44-66`; arranque `service_count: 20`) | Media |
| `docs/REPORTE-QA.md:3,44` | 152 pruebas backend | 302 recolectadas y en verde | Media |
| `docs/DOMAIN.md:3` | "Nada de lo aquí descrito está aplicado al código ni a la base" | Tipo `transfer`, triggers, centavos y migraciones `ledger-v1/v2` están aplicados | Alta |
| `docs/DATA-DICTIONARY.md:3` | "D1 no está aprobado; no se modificó la base" | Parte del modelo (transfer, centavos, restricciones) sí está aplicada; el volumen y perfiles de D1 no | Media |
| `docs/DATA-DICTIONARY.md:1568`; `docs/DISENO-DATOS-PLATAFORMA.md:18,69` | ~984 movimientos | 967 en la base real; una base nueva sembró 997 por depender de la fecha | Baja |
| `README.md:5` | Datos 100% sintéticos | Hay una meta con nombre de persona creada 2026-10-25; no puedo verificar su origen | Alta |
| `README.md:20` | Toda interacción con la UI regresa al agente | Solo compra y aportación emiten `ui_event`; otras tarjetas ofrecen "preguntar" como texto; filtros y toggles no regresan | Media |
| `docs/MIGRACION-FASE1.md:3,201,210` | Diseño para aprobación; "la base no se ha tocado" | `ledger-v1` y `ledger-v2` están aplicadas desde 2026-10-30 00:52:54; la tabla del libro fue reconstruida | Alta |
| `docs/MIGRACION-FASE1.md:79,157` | Fila 967 reclasificada a `goal_id=3` | La fila real tiene `goal_id=2`; el resultado de la migración sí registra 3 | Crítica |
| `docs/ESTADO-PROYECTO.md` anterior | 19 herramientas, 283 pruebas, base de 155,648 bytes | Documento obsoleto; esta versión lo reemplaza | Alta |
| `vercel.json:1-20` | Despliegue en tres servicios | No probado; SQLite/MCP stdio no encajan con un filesystem efímero | Media |

---

## 4. Riesgos y correcciones aplicadas

Los riesgos abiertos se ordenan por gravedad; R-1 quedó corregido en 2.1.

### R-1 (Corregido en 2.1) — La aportación duplicaba el monto y bloqueaba completar la meta

**Evidencia original:** `finance.py` actualizaba `saved_amount_cents` y luego `transfer_balance()` volvía a sumar el monto; el trigger `seed.py:123-133` se ejecutaba después de esa actualización. Reproducciones sobre copia:
- meta de $1,000 + abono de $1,000 -> HTTP 500 `IntegrityError: INV-4`;
- meta de $1,000 + abono de $500 -> 200, `saved_amount: 500`, `status: completada`.

**Corrección aplicada:** `finance.py:529-561` calcula `new_saved_cents` una sola vez, inserta la transferencia antes de actualizar el ahorrado y fija el estado según el resultado exacto. El trigger ahora valida contra el estado previo.

**Verificación:** 7 pruebas en `tests/test_transfer_accounting.py` (50%, 51%, 60%, 100%, retiro, semilla al 50% y API); el 100% completa la meta, el 50% permanece activa y el retiro la reabre. La base real no se reescribió; su desajuste es R-2.

### R-2 (Crítico) — El libro y las metas no cuadran, y la reconciliación lo oculta

**Evidencia:** consulta sobre copia de la base real:

| Meta | Ahorro registrado | Suma de transferencias | Diferencia |
|---|---:|---:|---:|
| 1 | $18,500 | $0 | +$18,500 |
| 2 | $8,200 | $22,500 | -$14,300 |
| 3 | $22,500 | $0 | +$22,500 |

La migración registró `id 967 -> goal_id 3`, pero la fila real tiene `goal_id=2`. La causa está en `migrate.py:310-317`: el `INSERT` de la fila reclasificada enumera `account_id, goal_id` pero pasa `plan[row["id"]]` y después `row["account_id"]`; el `account_id` original era 2 y la meta planeada 3, así que la fila terminó con `account_id=3` y `goal_id=2`. La verificación de la migración (`migrate.py:331-349`) solo compara totales, no el mapeo por fila, por eso no lo detectó. El defecto se reprodujo al restaurar el respaldo y ejecutar `ledger-v1/v2`: la fila 967 volvió a quedar `account_id=3, goal_id=2`. `reconcile.py:57-70` solo comprueba cotas y `reconcile.py:123-156` devuelve `ok: true`.

**Impacto:** el progreso de ahorro, el saldo total y la confianza en la base son incorrectos; la herramienta que debería detectarlo da una falsa señal verde.

**Corrección mínima:** corregir el orden de parámetros en `migrate.py` y añadir una comprobación por fila; agregar a `reconcile` la comparación `saved_amount_cents` contra `SUM(transfers)` y `status='completada'` contra objetivo; migración `ledger-v3` con respaldo que repare el movimiento 967 y los saldos; prueba sobre base real y base nueva.

### R-3 (Alto) — Una transferencia multi-cuenta se registra en una sola cuenta

**Evidencia:** `finance.py:478-502` reparte el débito entre cuentas con saldo; `finance.py:550-555` guarda un solo `account_id`. Prueba: abono de $50,000 debita $35,700 de la cuenta 2 y $14,300 de la cuenta 1, pero la fila de transferencia apunta solo a la cuenta 2. La fila histórica 967 apunta a la cuenta 3 por $22,500, cuyo saldo actual es $3,140.80.

**Impacto:** no se puede reconstruir el movimiento por cuenta; cualquier reporte o conciliación por cuenta es incorrecto.

**Corrección mínima:** tabla de piernas (`transfer_legs`) o una fila por cuenta; migrar la fila 967; probar el reparto y la reconstrucción de saldos.

### R-4 (Alto) — Validación inconsistente: estados inválidos, fechas pasadas y errores 500

**Evidencia:** `PATCH /goals/{id}` acepta `status: "banana"`, `deadline: "2000-01-01"` y un nombre con etiquetas; `finance.py:464-467` no valida. `POST /budget/update` con límite 0 devuelve 500 por el CHECK de la tabla. MCP acepta hasta $100,000,000 frente a $10,000,000 de REST y no sanea el nombre (`finance_tools.py:196-245`).

**Impacto:** metas en estados imposibles, presupuestos que rompen la pantalla y diferencias entre transportes.

**Corrección mínima:** una sola validación en `domain.py`; `Literal` para estado; fecha parseada; nombre saneado en POST/PATCH/MCP; mapear `ValueError`/`DomainError`/`IntegrityError` a 4xx; pruebas de paridad.

### R-5 (Alto) — PII y promesa de "datos 100% sintéticos"

**Evidencia:** la base real contiene una meta con nombre de persona creada 2026-10-25; 9 archivos versionados contienen rutas absolutas con el usuario local; README:5 afirma que los datos son 100% sintéticos.

**Impacto:** al publicar el repositorio o empaquetar la base se expone información personal; en modo en vivo esos nombres pueden enviarse al proveedor de IA.

**Corrección mínima:** inventario y limpieza de PII, redacción antes del proveedor, exclusión de rutas personales y corrección de la afirmación del README.

### R-6 (Medio) — "Disponible" significa dos cosas distintas

**Evidencia:** `DOMAIN.md:116` define disponible = saldo en cuentas; `finance.py:633` devuelve ingreso − gasto; `BudgetPlanner.tsx:20-21` vuelve a calcular ingreso − gasto en el cliente.

**Impacto:** la etiqueta "Disponible" puede mostrar un número negativo que no es el dinero disponible y duplica la métrica fuera del servidor.

**Corrección mínima:** una sola métrica calculada en el servidor, con nombre explícito ("balance del mes" o "disponible"); el cliente solo presenta.

### R-7 (Medio) — Salud ciega

**Evidencia:** `routes.py:117` usa `DB_PATH` sin importarlo; el `except` convierte el `NameError` en `size_bytes: null`. Verificado en `/api/health` con base temporal.

**Impacto:** monitoreo y diagnóstico sin tamaño de base; el error real queda oculto.

**Corrección mínima:** importar `config.DB_PATH` o `database.DB_PATH`, no silenciar el error y probar el campo.

### R-8 (Medio) — Portabilidad y empaquetado sin resolver

**Evidencia:** scripts `.cmd`, puertos fijos, dependencias sin fijar, `@next/swc-win32-x64-msvc@16.4.2` con `next@15.5.28`, MCP lanzado con `sys.executable` (`mcp_client.py:36-37`) y ruta asumida del repo (`finance_tools.py:18-21`).

**Impacto:** instalación/deploy frágil; un `.exe` relanzaría el propio ejecutable en vez de Python.

**Corrección mínima:** versiones fijas y `npm ci`; scripts multiplataforma; ruta de datos configurable; estrategia explícita de MCP para el paquete; decidir Vercel.

### R-9 (Medio) — Confirmaciones sin vigencia y API sin autenticación

**Evidencia:** `_PENDING` es un diccionario global sin TTL (`orchestrator.py:2278-2304`); `routes.py` no usa `Depends`/`Security`; `/agent/confirm` y las escrituras quedan abiertas.

**Impacto:** en local es aceptable; si se publica, cualquiera puede escribir o confirmar. Las acciones pendientes pueden quedar en memoria indefinidamente.

**Corrección mínima:** TTL, un solo uso, alcance por sesión/trace; autenticación y CSRF si hay despliegue público; declarar el modo local si no lo hay.

### R-10 (Bajo) — Documentación y repositorio desactualizados

**Evidencia:** cifras contradictorias de herramientas, pruebas, migraciones y volumen; 27 artefactos de depuración versionados más 4 de `.archify`; 203 archivos del skill vendido; línea corrupta en `.gitignore`.

**Impacto:** el evaluador o un nuevo desarrollador toma como verdad estados que ya no existen; el repositorio parece menos terminado de lo que es.

**Corrección mínima:** reescribir documentos con cifras verificadas, retirar artefactos y vendor innecesario, corregir `.gitignore`.

---

## 5. Lo que no pude verificar

- **Despliegue en Vercel:** no se ejecutó `vercel` ni se probó la URL; `vercel.json` existe.
- **Modo en vivo con claves reales:** no hay claves en el entorno; solo se revisó el código y el modo demo.
- **Accesibilidad real:** no se ejecutó axe, Lighthouse ni prueba con lector de pantalla.
- **Empaquetado `.exe`:** no se generó ni probó un binario.
- **Pruebas de navegador/E2E:** no hay Playwright/Cypress; las 9 pruebas de frontend son análisis estático de archivos.
- **Rollback completo:** se restauró el respaldo en una copia, se migró y se probó con la app; no se probó volver a una versión anterior del código ni un rollback en producción.
- **Concurrencia multiproceso:** no se probaron dos confirmaciones simultáneas ni múltiples instancias.
- **Origen de la meta 4:** no puedo determinar si el nombre corresponde a una persona real o es un dato inventado; por prudencia se trata como PII.
- **Historia completa de secretos:** se revisó el árbol actual y los commits disponibles; no se hizo un escaneo forense de toda la historia.
- **Vulnerabilidades de dependencias:** no se ejecutó `npm audit` ni `pip-audit`; solo se verificaron versiones e incompatibilidad de `swc`.
- **Rendimiento a escala:** solo se midió la base de 967 movimientos; no hay prueba de volumen ni carga.
- **OCR de capturas:** no se revisaron las imágenes de `docs/ui-evidence` para detectar PII.

---

## 6. Evidencia de integridad y cumplimiento de solo lectura

**Base real:** `backend/data/banorte.db`

| Comprobación | Antes | Después |
|---|---|---|
| SHA-256 | `48AED47499A0141ABAD80308AAE9B0CF506E37F6C05C49C77F77B5393AC287BB` | Igual |
| Tamaño | 237,568 bytes | Igual |
| Fecha UTC | 2026-10-30T00:52:54.3234366Z | Igual |

Las pruebas, los arranques y las reproducciones de escritura usaron copias en `%TEMP%\opencode\audit\` o `BANORTE_DB_PATH` temporal. No se escribió en la base real. Al cierre, `git status --porcelain` muestra `finance.py` modificado, `tests/test_transfer_accounting.py` nuevo y los dos documentos de la auditoría. No se hicieron commits.

**Comandos y resultados principales**

| Comprobación | Resultado |
|---|---|
| `pytest backend/tests` con base temporal | `302 passed in 530.42s` |
| `npm test` en `frontend` | 9 pruebas, 0 fallos |
| `npx tsc --noEmit` | exit 0 |
| `npm run build` | exit 0, Next.js 15.5.28 |
| Arranque con copia de la base real | `/api/health` 200, schema `ledger-v2`, 20 herramientas MCP |
| Arranque con base nueva | 200, siembra 3 cuentas, 3 metas, 12 presupuestos, 997 movimientos, integridad `ok` |
| Restauración del respaldo + migraciones | Integridad `ok`, 0 FK, 967 movimientos, `ledger-v1/v2`; fila 967 `account_id=3, goal_id=2` (defecto reproducido) |
| App contra respaldo restaurado y migrado | `/api/health` 200 (`ledger-v2`, 7 tablas); `/api/dashboard` y `/api/goals` 200 con 4 metas |
| Aportación que completa la meta (2.1) | HTTP 200, `status: completada`; antes 500 |
| Aportación al 50% (2.1) | HTTP 200, `saved_amount: 500`, `status: activa`; antes completada |
| Reproducción de presupuesto 0 | HTTP 500 |
| `PATCH` inválido | HTTP 200 con `status: banana`, fecha 2000 y nombre con etiquetas |

El respaldo original es de antes de centavos: `transactions.amount` es `REAL`, no existe `amount_cents` y `schema_migrations` está vacío. Restaurarlo exige ejecutar `ledger-v1/v2`; sin migración, la app actual no puede leerlo.

---

## 7. Conclusión

El valor real del proyecto está en el contrato de interfaz, la separación de capas y la infraestructura de pruebas; eso es más que un demo. El flujo central de aportaciones quedó corregido en 2.1: ya se puede completar una meta, el 50% no se marca completa y el retiro la reabre. Siguen abiertos el desajuste libro-metas (R-2), la semilla de metas 1–2 (2.6) y el débito multi-cuenta (R-3); mientras la Etapa 2 no esté cerrada, la base debe tratarse como demostración y no como libro contable.

El siguiente paso está fijado en `docs/PLAN.md`, tarea **2.3**.
