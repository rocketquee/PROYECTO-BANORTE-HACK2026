# Guion de demo — Banorte AI Finanzas (5 pasos)

Duración objetivo: **4–5 minutos**. Todo corre sobre datos sintéticos y una base
SQLite local; ninguna escritura mueve dinero real.

El catálogo A2UI tiene **9 componentes** por decisión de producto: los 5
originales más `PlanDePago`, `LineChart`, `Slider` y `BudgetAllocator`.
Ninguno se retiró.

## Preparación

1. Desde la raíz del repositorio:

   ```powershell
   scripts\start-all.cmd
   ```

   El script propaga `BANORTE_DEMO_TODAY` al backend, al servidor MCP y al
   frontend, de modo que "hoy" es la misma fecha en toda la demo.

2. Abre la aplicación y entra a **Asistente** (segundo elemento del menú).
3. Comprueba que el indicador de salud diga **IA activa**. Si dice *Ayuda local*,
   el paso 5 ya está ocurriendo: explica la degradación y continúa.
4. Ten a la mano `docs/DEMO-SCRIPT.md` y no escribas mensajes distintos a los
   indicados: cada frase está probada contra el catálogo A2UI.

---

## Paso 1 — Saldo (lectura, sin confirmación)

**Mensaje exacto:**

```
¿Cuánto dinero tengo?
```

**Componente esperado:** `StatCard` con el **Saldo total** en cuentas de
demostración.

**Narración:**

> "El asistente no inventa la cifra: consulta el saldo con la herramienta MCP
> `get_balance`, que lo calcula en centavos enteros en la capa de dominio. La
> respuesta es solo lectura y no pide confirmación."

**Qué mirar:** la tarjeta muestra el mismo importe que la pantalla *Inicio*.

---

## Paso 2 — Análisis (tendencia de gasto)

**Mensaje exacto:**

```
¿Cómo han cambiado mis gastos en los últimos 6 meses?
```

**Componente esperado:** `LineChart` con la serie mensual de gasto y su periodo
declarado.

**Narración:**

> "Cada punto viene de `get_spending_trend`. El modelo elige el componente y
> copia la serie; no recalcula porcentajes ni sumas. El plan se valida contra
> los resultados de la herramienta antes de renderizarse, así que una cifra
> inventada se rechaza."

**Qué mirar:** el periodo visible y la nota con el cambio entre el primer y el
último mes.

---

## Paso 3 — Meta (avance de ahorro)

**Mensaje exacto:**

```
¿Cómo van mis metas de ahorro?
```

**Componente esperado:** `ProgressRing` con el avance de una meta sembrada
(*Fondo de emergencia* o *Viaje a Japón*).

**Narración:**

> "El avance también lo calcula el dominio: ahorrado entre objetivo. El
> asistente solo lo presenta."

**Qué mirar:** el anillo, el monto ahorrado y el objetivo.

---

## Paso 4 — Acción (ciclo cerrado con confirmación)

**Mensaje exacto:**

```
Quiero abonar $500 a Viaje a Japón.
```

**Componente esperado:** `TransferForm` con el monto, la meta y el texto de
confirmación. El servidor ya emitió `confirmation_token` e `idempotency_key`.

**Narración:**

> "Preparar el abono no escribe nada. El formulario es la propuesta; el botón
> envía un evento de interfaz verificado en el servidor. Solo entonces el
> dominio aplica la transferencia, de forma atómica e idempotente."

**Acción en pantalla:** pulsa **Confirmar abono**.

**Resultado esperado:** el asistente responde *"Listo. Registré un abono de
$500.00 a «Viaje a Japón»…"* y el nuevo `ui_plan` muestra:

- un `StatCard` **Abono aplicado** por `$500`, y
- un `ProgressRing` actualizado.

**Narración de cierre:**

> "El saldo de la meta subió exactamente $500 y se registró una transferencia
> con sus dos piernas. La reconciliación de invariantes sigue en verde. Si se
> repite el clic, la clave de idempotencia evita duplicar el movimiento."

**Verificación opcional:** abre *Ahorro* y confirma que *Viaje a Japón* subió
$500; abre *Movimientos* y verifica una sola transferencia.

---

## Paso 5 — Degradación en vivo (sin reiniciar el backend)

**Objetivo:** demostrar que el producto sigue respondiendo con el motor local
cuando el proveedor de IA desaparece a mitad de la demo.

**Requisito:** Ollama instalado y el backend arrancado con el proveedor local:

```powershell
ollama serve
ollama pull llama3.2
$env:LLM_PROVIDER = "ollama"
$env:LLM_MODEL = "llama3.2"
$env:LLM_BASE_URL = "http://localhost:11434/v1"
$env:LLM_API_KEY = "ollama"
scripts\start-all.cmd
```

**Antes de la caída:** comprueba que el proveedor está sano y que una petición
en modo `think` usa el modelo real:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health |
  Select-Object -ExpandProperty provider | ConvertTo-Json

$body = @{
  message = "¿Cuál es mi saldo?"
  mode = "think"
  session_id = "demo-live"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/agent/chat `
  -ContentType "application/json" -Body $body |
  Select-Object mode, degraded, reason | ConvertTo-Json
```

Esperado: `provider.mode = "live"` y la respuesta `mode = "live"`.

**Caída en vivo:** sin tocar el backend, detén Ollama:

```powershell
Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force
```

**Mensaje exacto:** repite la misma petición `mode = "think"` con el mismo
cuerpo. El backend sigue encendido; solo desapareció el proveedor.

**Resultado esperado:** la petición no devuelve 500. Devuelve:

- `mode = "demo"`,
- `degraded = true`,
- `reason = "provider_unavailable"`,
- un `ui_plan` válido con `StatCard` de saldo.

El camino está en `backend/app/services/agent/loop.py:386-404`: cualquier
`ProviderError`, timeout o fallo del proveedor se convierte en
`_demo_fallback(...)`. La cifra sigue viniendo de la misma herramienta MCP.

**Nota sobre el indicador:** `/api/health` devuelve el estado cacheado del
arranque (`backend/app/services/agent/providers.py:427`,
`backend/app/main.py:44-59`), así que la cabecera puede seguir diciendo
*IA activa* hasta reiniciar el backend. La verdad por petición es `degraded`
en la respuesta del chat.

**Alcance de la interfaz:** el cliente web actual envía `mode=demo`
(`frontend/src/components/AgentView.tsx:82-87`), de modo que este paso se
demuestra contra la API con `mode=think`; la interfaz sigue usando el motor
local. Para verlo desde la UI hace falta la propuesta de abajo.

**Por qué no se cambia `LLM_BASE_URL` en caliente:** `backend/app/core/config.py:24`
lee la variable al importar el módulo y
`backend/app/services/agent/providers.py:455` construye el proveedor con ese
valor. Cambiar la variable de entorno de un proceso ya iniciado no es posible
desde fuera en Windows; exigiría reiniciar el backend. Para una caída sin
reinicio, mata el proceso local.

**Alternativa sin Ollama (propuesta, no implementada):** un endpoint de
desarrollo `POST /api/dev/provider/degrade` protegido por `DEV_MODE` que fije
`_health_status` en `mode="demo"`, y otro `POST /api/dev/provider/recheck` que
vuelva a ejecutar `check_provider_health()`. Permitiría ensayar la caída y la
recuperación desde la interfaz sin matar procesos. Hoy no existe; la vía limpia
es detener Ollama.

---

## Cierre (30 segundos)

> "Todo lo que vieron es verificable: catálogo A2UI estricto, cifras
> fundamentadas en herramientas MCP, escrituras solo tras confirmación
> verificada y una suite que compara el hash de la base real antes y después
> para probar que las pruebas no la tocan."

## Mensajes de respaldo (si el presentador se adelanta)

| Paso | Mensaje | Componente |
|---|---|---|
| 1 | `¿Cuál es mi saldo?` | `StatCard` |
| 2 | `¿En qué gasté este mes?` | `BarChart` |
| 3 | `Muéstrame mis últimos movimientos.` | `Table` |
| 4 | `Quiero abonar $500 a Fondo de emergencia.` | `TransferForm` |

No cambies el monto ni el nombre de la meta en el paso 4 sin volver a ensayar:
la confirmación valida monto, meta, token e idempotencia contra el estado del
servidor.
