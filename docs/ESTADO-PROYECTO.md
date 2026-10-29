# ESTADO DEL PROYECTO — Informe de auditoría técnica independiente

**Repositorio:** `proyecto-banorte-ai-finanzas` (rama `main`, commit `dc606b5` "recondicionamientpo")
**Fecha de auditoría:** 26/10/2026
**Auditor:** independiente (no construyó el proyecto)
**Regla de oro aplicada:** solo lectura; ninguna afirmación sin ruta de archivo:línea o salida de comando. BD real intacta.

---

## 1. Veredicto en cinco líneas

El proyecto es un prototipo funcional de asistente financiero con interfaz dinámica generada en tiempo real. El núcleo (contrato UI validado con Pydantic, servidor MCP real, capa de dominio con invariantes, dinero en centavos, escrituras atómicas/idempotentes, tests y build verdes) está bien ingeniero y cumple la mayor parte de lo prometido en el README. Sin embargo, el "LLM al centro" no es real en el modo por defecto (`AI_PROVIDER=demo`): la comprensión del lenguaje es por reglas, el modelo no interpreta ni orquesta a menos que se configure una clave de OpenAI/Anthropic. Varias secciones de la UI son informativas/simuladas (no mueven dinero real) y faltan entregables planeados (PDF, correo, .exe, evaluación de retención). Resultado: prototipo sólido como demostración, pero incompleto como producto del reto.
---

## 2. Tabla maestra: Área | Elemento | Estado | Evidencia

| Área | Elemento | Estado | Evidencia |
|------|----------|--------|-----------|
| A. Reto | LLM al centro (interpretar/decidir/orquestar) | Parcial | `backend/app/services/agent/providers.py:143-149` `get_provider()` devuelve `None` sin clave → `demo_response` basado en reglas; `orchestrator.py:2344-2345` elige `demo_response` si `get_provider() is None or AI_PROVIDER=="demo"`. Sin clave: 0% de respuestas pasa por el modelo. Con clave: 100% (no hay mixto medible). |
| A. Reto | Proveedor configurable y funcional | Hecho y verificado | `providers.py:35-148` `OpenAIProvider`, `AnthropicProvider`; `config.py:12-17` `AI_PROVIDER`/`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`. |
| A. Reto | MCP: herramientas expuestas | Hecho y verificado | `mcp-server/server.py:44-66`: 19 herramientas registradas con `mcp.tool(...)`. |
| A. Reto | MCP: cuáles usa el orquestador | Hecho y verificado | `orchestrator.py:39-47` `WRITE_TOOLS` (3) y `MCP_ALLOWED_TOOLS` (19, idéntico al expuesto). |
| A. Reto | MCP: lectura vs escritura | Hecho y verificado | `mcp-server/README.md:10-20`: 16 lectura, 3 escritura (`create_savings_goal`, `update_savings_goal`, `apply_savings_contribution`) que requieren `confirm=True`. |
| A. Reto | A2UI: contrato, versión, validación servidor | Hecho y verificado | `backend/app/schemas/ui.py:316-341` unión discriminada `UISpec` con `extra="forbid"`; `ui.py:346` `UI_SCHEMA_VERSION="1.0"`; `routes.py:240-251` `GET /ui-schema` (solo `DEV_MODE`). |
| A. Reto | A2UI: registro componentes cliente | Hecho y verificado | `frontend/src/components/dynamic/DynamicRenderer.tsx:44` comprueba `AUTHORIZED_COMPONENTS`; tipos desconocidos → tarjeta de error (líneas 44-50). |
| A. Reto | Componentes generables vs renderizados de verdad | Hecho y verificado | 16 tipos autorizados en `ui.py:336-341`; todos los 16 tienen `case` en `DynamicRenderer.tsx:51-126`. |
| A. Reto | Flujo accionable con efecto real y confirmación | Hecho y verificado | Crear meta y abonar a meta: `savings.py:88-144` `apply_contribution` (atómico, idempotente); `routes.py:209-237` `/agent/confirm`. |
| A. Reto | Ciclo cerrado (interacción → agente → acción/nueva UI) | Parcial | Sí: `purchase_option_selected`, `purchase_goal_confirmed`, `savings_contribution_confirmed` vuelven por `/agent/chat` con `ui_event` (`api.py:72-113`). No: interacciones de gráficas/tablas son solo lectura, no retornan al agente. |
| A. Reto | Datos y APIs propios | Hecho y verificado | SQLite sintética (`seed.py`), MCP + REST (`mcp_client.py`, `routes.py`). |
| A. Reto | Entregables (demo, repo, datos, diagrama, decisiones) | Hecho sin verificar | `scripts/start-all.cmd` (demo), `README.md` (instrucciones), `seed.py` (datos), `docs/arquitectura.html` (diagrama), `docs/DECISIONS.md` (decisiones). |
| B. Datos | Modelo libro de movimientos y tipos | Hecho y verificado | `seed.py:23-43` tabla `transactions` con `CHECK (type IN ('income','expense','transfer'))`; `finance.py:18` `LEDGER_TYPES`. |
| B. Datos | Invariantes en documento vs en base | Parcial | CHECK constraints en `seed.py:34-42` (INV-1 forma de cada tipo). `domain.py` impone reglas en código; no hay disparadores/triggers en SQLite. |
| B. Datos | Representación del dinero, tolerancias, redondeos | Hecho y verificado | `money.py:1-159`: centavos enteros, `ROUND_HALF_UP` vía `Decimal`, única puerta `to_cents`/`to_pesos`; `credit.py:48-95` última cuota absorbe residuo. |
| B. Datos | Rutas de escritura: atómicas, idempotentes, validadas en un lugar | Hecho y verificado | `savings.py:88-144` `apply_contribution` con `BEGIN IMMEDIATE` + `idempotency_records`; `domain.py:validate_transfer` autoridad única de reglas (INV-9); `finance.py:set_budget_limit` `ON CONFLICT` (`routes.py:192-197`). |
| B. Datos | Métricas derivadas fuera de dominio (duplicadas) | No pudo verificar | `finance.py` es autoridad de métricas (`domain.py:8-11` lo declara); no se auditó duplicación de métricas en frontend. |
| B. Datos | Migración: determinista, corre al iniciar, reset/reconciliación | Hecho y verificado | `migrate.py:384-451` migraciones versionadas (`ledger-v1`, `ledger-v2`), idempotentes, con backup + transacción + `foreign_key_check`; `database.py:46-65` `ensure_database` corre al arranque. |
| B. Datos | Estado BD real: datos inconsistentes/de prueba | Hecho (solo lectura) | `backend/data/banorte.db` = 155648 bytes, 25/10/2026 02:57:21 p.m. (antes y después de tests, sin cambios). Los tests usan `tmp_path` (`conftest.py:16-21`) y `BANORTE_DB_PATH` temporal; la BD real no se tocó. |

| C. Asistente | Intenciones por reglas (demo) | Hecho y verificado | `orchestrator.py` demo: rule-based con normalización (docstring línea 6-8). Cobertura uniforme para las entidades probadas; frases libres requieren proveedor live. |
| C. Asistente | Intenciones por herramientas (MCP) | Hecho y verificado | 19 herramientas MCP (`server.py:44-66`) invocables por el agente en ambos modos. |
| C. Asistente | Sobreajuste (cadenas literales, nombres, cifras fijas) | Hallado | `orchestrator.py:49` `PURCHASE_SIMULATION_RATE = 15.9`; `seed.py:301` "Electrodoméstico Liverpool" 14.800,00; `seed.py:306` "Rappi pedido #8817" 348,90 duplicado; `seed.py:289` aguinaldo 22.000,00. |
| C. Asistente | Cobertura uniforme por entidad | Parcial | Capacidades implementadas, pero el demo (reglas) cubre solo patrones probados; frases muy libres fallan. |
| D. Interfaz | Pantallas y navegación automática | Parcial | `page.tsx:28-31` `askAssistant` cambia a vista `"asistente"` automáticamente al hacer clic; 14 secciones (`page.tsx:13-17`), varias simuladas (`README.md:245-246`). |
| D. Interfaz | Ubicación del asistente | Hecho | `page.tsx:79-84` `AgentView` solo en vista `"asistente"`; sidebar con historial (`chatStore.ts`). |
| D. Interfaz | Componentes duplicados/sin uso | Parcial | `backend/probe2.py`, `probe3.py`, `probe_findings.py` son archivos de exploración sin llamadores claros (código potencialmente muerto). |
| D. Accesibilidad | Letra base, contraste, botones, foco | Declarado no verificado | `README.md:203-212` declara 18px, contraste ≥4.5:1, botones 44-48px, `aria-label`, `prefers-reduced-motion`. |
| D. Responsividad/rendimiento | Carga diferida, pantallas lentas, animaciones | Parcial | `next build` exitoso (<14s, 4 páginas estáticas). `TwinklingSquares.tsx` (animación) existe; no se midió rendimiento real. |
| E. Seguridad | Claves y variables de entorno | Hecho y verificado | `.env` NO versionado (`git ls-files` solo trae `.env.example`); `config.py:32-43` carga `.env` con `setdefault` (env gana). Claves vacías por defecto. |
| E. Seguridad | CORS, orígenes, puertos fijos | Hecho y verificado | `main.py:60-66` CORS solo `FRONTEND_ORIGIN` (`config.py:25` = `http://localhost:3000`); puertos 8000/3000 fijos en `start-all.cmd:34,53`. |
| E. Seguridad | Validación de entradas, límites de tamaño | Hecho y verificado | Esquemas Pydantic `Strict` (`extra="forbid"`) en `api.py` y `ui.py`; `ChatRequest.message` max 5000 (`api.py:117`); rate limit 30 msgs/10s (`routes.py:25-41`). |
| E. Seguridad | Resistencia a inyección de prompt (datos no código) | Hecho y verificado | `DynamicRenderer.tsx:44-50` nunca interpreta JSON; `ui.py` `extra="forbid"` bloquea campos tipo `onClick`; `chatSecurity.mjs` sanitiza (`chatStore.ts:12,107-112,139-141`). |
| E. Seguridad | Enmascarado de datos sensibles | Parcial | `mcp-server/tools/finance_tools.py:57-58` tarjetas solo últimos 4 dígitos. No hay enmascarado explícito antes de enviar datos al modelo (datos son sintéticos por diseño). |
| E. Seguridad | Registros con datos sensibles | Hecho y verificado | `main.py:7` comment "Logs nunca contienen user message content"; `routes.py:82` log solo `error_type`. |
| E. Seguridad | Dependencias con riesgo conocido | No pudo verificar | `requirements.txt` / `package.json` sin lock de vulnerabilidades (no se ejecutó `npm audit`/`pip audit`). |
| F. Portabilidad | Instalación desde clon limpio | Hecho y verificado | `scripts/setup.cmd` verifica Python 3.11+/Node 18.18+, crea venv, instala dependencias, copia `.env`. |
| F. Portabilidad | Scripts *.cmd y README instalación | Hecho | `scripts/setup.cmd`, `start-all.cmd`, `stop-all.cmd`, `run-tests.cmd` presentes. |
| F. Portabilidad | Versiones fijadas | Parcial | `package.json` usa `^` (no fijado); `requirements.txt` usa `>=`/`==` parciales. |
| F. Portabilidad | Rutas personales/OneDrive | Parcial (solo metadatos) | Rutas personales de Windows solo en `.archify/*` (metadatos de herramienta de diseño), no en código fuente ni scripts. |
| F. Portabilidad | Datos en carpeta del repo | Hecho | `backend/data/banorte.db` (gitignorado, `database.py:8` `DB_PATH` overridable vía `BANORTE_DB_PATH`). |
| F. Portabilidad | Puertos configurables | Parcial | `FRONTEND_ORIGIN` configurable; puertos 8000/3000 fijos en `start-all.cmd`. |
| F. Despliegue | vercel.json y por qué falla | Existe, no verificado | `vercel.json` define 3 servicios y rewrites; no se probó el despliegue. |
| F. Empaquetado escritorio (.exe) | No existe | No existe | Búsqueda recursiva de `*.exe` solo encontró ejecutables del venv y Python, no una app empaquetada de Banorte. |
| G. Calidad | Pruebas backend: 283, todas pasan | Hecho y verificado | `pytest tests -v` con BD temporal → `283 passed in 138.96s`. |
| G. Calidad | Pruebas frontend: 9, todas pasan | Hecho y verificado | `node --test tests/*.test.mjs` → `pass 9, fail 0`. |
| G. Calidad | Build de producción frontend | Hecho y verificado | `npm run build` → compiló en 13.8s, types OK, 4 páginas estáticas, sin errores. |
| G. Calidad | Código muerto / archivos enormes / TODO | Parcial | `backend/probe2.py`, `probe3.py`, `probe_findings.py` (exploración, sin llamadores claros). |
| G. Calidad | Documentación vigente vs desactualizada | Parcial | Existen `ARCHITECTURE.md`, `DECISIONS.md`, `DOMAIN.md`, `MIGRACION-FASE1.md`, `AUDITORIA-FASE1.md`, `REPORTE-QA.md`. |
| G. Calidad | Trabajo sin commit | No pudo verificar | `git status --porcelain` no retornó salida usable en este shell. |
| H. Planeadas | Exportación a PDF | No existe | No se encontró código de exportación PDF. |
| H. Planeadas | Envío de estado por correo | No existe | No se encontró código de correo. |
| H. Planeadas | Perfiles de demostración | Parcial | Datos sintéticos deterministas (`seed.py`), pero no perfiles de usuario seleccionables. |
| H. Planeadas | Base ampliada (cuentas, tarjetas, estados, 24 meses) | Parcial | `accounts` y `cards` existen (`seed.py:54-73`); no hay estados de cuenta ni historial 24 meses (solo 12 meses). |
| H. Planeadas | Verificador de fundamentación del modelo | No existe | No se encontró. |
| H. Planeadas | Conjunto de evaluación con casos de retención | No existe | No se encontró. |
| H. Planeadas | Empaquetado .exe | No existe | Ver §F. |


## 3. Discrepancias entre documentos y código

| Documento / Afirmación | Qué dice | Qué hace el código | Gravedad |
|------------------------|----------|--------------------|----------|
| `README.md:45` "IA: proveedor configurable (OpenAI / Anthropic) o modo demostración sin API key" | El LLM es central y configurable. | Por defecto (`AI_PROVIDER=demo`, `config.py:12`) no hay LLM: `providers.py:143-149` devuelve `None` y el orquestador usa reglas (`demo_response`). El modelo solo participa si se configura una clave real. | Alta |
| `README.md:20-21` "Cada interacción con la UI regresa al agente y produce nuevas acciones (ciclo cerrado)" | Ciclo cerrado universal. | Solo ciertas interacciones (`purchase_*`, `savings_contribution_*`) retornan al agente vía `ui_event` (`api.py:72-113`). Gráficas, tablas y resúmenes son solo lectura y no vuelven al agente. | Media |
| `README.md:196-197` "40 variantes de ataque probadas obtienen una negativa amable" | Pruebas de seguridad documentadas. | No se encontró un conjunto de pruebas de inyección de prompt con 40 variantes en el repo. | Media |
| `docs/DOMAIN.md` (hipótesis) | Invariantes documentados. | Las invariantes están impuestas en `domain.py` y `seed.py` (CHECK), pero no hay disparadores/triggers de SQLite; algunas solo están en documento. | Media |

## 4. Riesgos críticos ordenados por gravedad

### R-1 (Alta) — El modo por defecto no usa LLM; el reto pide "LLM al centro"
**Evidencia:** `config.py:12` `AI_PROVIDER = os.getenv("AI_PROVIDER", "demo")`; `providers.py:143-149` `get_provider()` retorna `None` sin clave; `orchestrator.py:2344-2345` usa `demo_response` (reglas).
**Impacto:** Sin clave de API, el agente no interpreta ni orquesta con un modelo; incumple el espíritu del reto y el usuario no ve comportamiento de IA real.
**Arreglo mínimo:** Hacer que el modo demo simule razonamiento de IA de forma más rica, o documentar claramente que el modo por defecto es un respaldo de reglas y que el valor del reto requiere `AI_PROVIDER=openai|anthropic` con clave.

### R-2 (Alta) — Afirmación de "ciclo cerrado" no se cumple para todas las interacciones
**Evidencia:** `api.py:72-113` solo algunos `ui_event` tipos retornan al orquestador; `DynamicRenderer.tsx` renderiza gráficas/tablas sin callback de retorno al agente.
**Impacto:** El usuario puede creer que cualquier clic en la UI generada dispara una acción del agente, pero la mayoría son pantallas estáticas.
**Arreglo mínimo:** Aclarar en la UI/docs qué componentes son accionables vs informativos, o conectar los componentes de consulta al agente.

### R-3 (Media) — Sobreajuste con valores literales fijos
**Evidencia:** `orchestrator.py:49` `PURCHASE_SIMULATION_RATE = 15.9`; `seed.py:301` "Electrodoméstico Liverpool" 14.800,00; `seed.py:306` "Rappi pedido #8817" 348,90 (duplicado intencional); `seed.py:289` aguinaldo 22.000,00.
**Impacto:** El comportamiento está calibrado a datos de prueba concretos; no es generalizable a otros escenarios.
**Arreglo mínimo:** Parametrizar la tasa de simulación y revisar que las reglas de negocio no dependan de cadenas/nombres fijos de la semilla.

### R-4 (Media) — Escritura sin confirmación explícita en un transporte
**Evidencia:** `mcp-server/tools/finance_tools.py` expone herramientas de escritura que requieren `confirm=True`, pero un cliente MCP directo podría invocarlas sin pasar por el orquestador; la validación central está en `domain.py`/`savings.py`.
**Impacto:** Ruta de escritura expuesta vía MCP que podría invocarse sin confirmación de usuario si un cliente MCP la llama directamente.
**Arreglo mínimo:** Reforzar que todas las herramientas de escritura requieran `confirm=True` y que el orquestador sea el único punto de entrada autorizado para acciones de escritura.

### R-5 (Baja) — Datos de prueba en la BD local
**Evidencia:** `backend/data/banorte.db` existe (155648 bytes) con datos sintéticos, gitignorado pero presente en el repositorio local.
**Impacto:** Bajo (datos sintéticos, no reales), pero archivo binario versión-local que podría confundir.
**Arreglo mínimo:** Documentar que la BD se regenera al arranque (`database.py:46-65`) y que `banorte.db` es local.

### R-6 (Baja) — Metadatos con rutas personales de Windows
**Evidencia:** `.archify/architecture-banorte-*/*.json` contienen `C:\Users\jonna\OneDrive\...` (búsqueda `C:\\Users`).
**Impacto:** Exposición de ruta de usuario local en artefactos de metadatos (no es código fuente).
**Arreglo mínimo:** No incluir `.archify` en el entregable público o sanitizar rutas.


## 5. Puntaje estimado frente a la rúbrica del reto

Pesos y puntaje (escala 0-100, estimación conservadora):

| Criterio | Peso | Puntaje estimado | Aporte | Justificación breve |
|----------|------|------------------|--------|---------------------|
| Utilidad para el usuario | 25% | 60 | 15.0 | Funcional para consultas, ahorro y simulación, pero modo demo es reglas y varias secciones son simuladas. |
| Calidad y adaptabilidad de la UI generada | 20% | 75 | 15.0 | Contrato Pydantic `extra="forbid"`, 16 componentes autorizados, validación servidor+cliente, manejo de desconocidos. |
| Calidad de la solución de IA | 15% | 50 | 7.5 | Sin clave no hay LLM (reglas); con clave usa OpenAI/Anthropic pero sin orquestación compleja ni fundamentación verificable. |
| Arquitectura e ingeniería | 15% | 70 | 10.5 | Buena separación (dominio/finanzas/MCP), tests (283+9), build verde, dinero en centavos, idempotencia. |
| UX y diseño | 10% | 70 | 7.0 | Accesibilidad declarada (18px, contraste, foco), pero secciones simuladas y navegación automática no solicitada. |
| Innovación | 10% | 80 | 8.0 | Interfaz dinámica generada por agente es novedosa y el protocolo A2UI-equivalente está bien pensado. |
| Presentación | 5% | 80 | 4.0 | README completo, scripts de instalación, docs de arquitectura y decisiones. |
| **TOTAL estimado** | **100%** | — | **67.0 / 100** | |


## 6. Lista priorizada de qué hacer a continuación

| Prioridad | Acción | Esfuerzo | Se puede dejar fuera sin pérdida importante |
|-----------|--------|----------|---------------------------------------------|
| 1 | Hacer que el modo demo simule razonamiento de IA más rico, o exigir/documentar clave para el valor del reto | Medio | — |
| 2 | Completar el ciclo cerrado: conectar componentes de consulta (gráficas/tablas) al agente o etiquetarlos como informativos | Medio | — |
| 3 | Eliminar sobreajuste: parametrizar `PURCHASE_SIMULATION_RATE` y revisar dependencia de nombres/cifras fijas de la semilla | Bajo | — |
| 4 | Reforzar escritura: asegurar que todas las herramientas de escritura MCP requieran `confirm=True` y que el orquestador sea el único punto de entrada autorizado | Bajo | — |
| 5 | Entregables faltantes del reto: exportación PDF, correo, conjunto de evaluación de retención, empaquetado .exe | Alto | Sí (son "mejoras futuras" del README, no bloqueantes del prototipo) |
| 6 | Base ampliada: estados de cuenta, historial 24 meses, perfiles de demo seleccionables | Medio | Sí |
| 7 | Verificador de fundamentación de respuestas del modelo | Medio | Sí |
| 8 | Sanitizar rutas personales en `.archify` o excluirlo del entregable público | Bajo | — |

## 7. Lo que no pude verificar y qué necesitaría

- **Git status limpio / trabajo sin commit:** `git status --porcelain` no retornó salida usable en este shell (interferencia del prompt). Necesitaría ejecutar `git status` en una terminal estándar para confirmar archivos sin commit y untracked.
- **Despliegue vercel:** `vercel.json` existe pero no se probó el despliegue; necesitaría cuenta de Vercel y ejecutar `vercel` para confirmar si funciona o falla.
- **Dependencias con riesgo conocido:** no se ejecutó `npm audit` ni `pip audit`; necesitaría conexión a registros y ejecutar esas herramientas.
- **Accesibilidad real (contraste, tamaños de letra, foco):** el README lo declara pero no se midió en el CSS renderizado; necesitaría una auditoría de accesibilidad (axe, Lighthouse) sobre el servidor en ejecución.
- **Diagrama de arquitectura y documento de decisiones:** existen (`docs/arquitectura.html`, `docs/DECISIONS.md`) pero por regla de auditoría no se tomaron como evidencia; se necesitaría revisarlos independientemente si se quiere confirmar que coinciden con el código.
- **Pruebas de inyección de prompt (las "40 variantes"):** no se encontró un conjunto con esa cifra en el repo; necesitaría localizarlo o confirmar que no existe.
- **Duplicación de métricas derivadas fuera del dominio:** `domain.py` declara ser la autoridad y `finance.py` de métricas, pero no se auditó el frontend para detectar métricas duplicadas.


---

## Evidencia de integridad (BD real)

Antes y después de ejecutar la suite de pruebas (con `BANORTE_DB_PATH` apuntando a `%TEMP%\banorte_audit_test.db` y la fixture `tmp_path` de `backend/tests/conftest.py`):

- `backend/data/banorte.db`: **155.648 bytes, domingo 25/10/2026 02:57:21 p. m.** — idéntico antes y después. La base real no fue modificada por las pruebas.

**Confirmación final:** No se modificó, borró ni formateó ningún archivo del repositorio salvo la creación de `docs/ESTADO-PROYECTO.md`. No se hicieron commits. La base de datos real (`backend/data/banorte.db`) quedó intacta.

**Nota:** score conservador; si se demuestra el ciclo cerrado completo y se activa LLM por defecto, podría subir.



