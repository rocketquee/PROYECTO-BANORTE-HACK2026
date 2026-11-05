# Reglas del repositorio — Banorte AI Finanzas

Estas reglas aplican a cualquier persona o agente que modifique este proyecto.
Se derivan de `docs/PLAN.md` y de las sesiones de corrección de la Fase A.

## 1. Evidencia obligatoria

- Ninguna afirmación se acepta sin `archivo:línea` o salida de comando.
- Toda puerta de salida se demuestra ejecutando la comprobación, no describiéndola.
- Los comandos de verificación viven en la documentación y deben ser reproducibles.

## 2. Causa raíz, no parches puntuales

- Se corrige la causa en la capa que corresponde (dominio, semilla, herramienta),
  nunca con una excepción para una entidad, una meta o una prueba concreta.
- Si un comportamiento debe ser uniforme para todas las entidades del mismo tipo,
  la corrección va en la capa de dominio compartida.
- Prohibido añadir `xfail`, `skip` o exclusiones para tapar fallos.

## 3. Fecha de referencia única

- `seed.reference_today()` (backend) es la **única** fuente de "hoy" del proyecto.
- La usan la semilla, el backend, el agente, las herramientas MCP y las pruebas.
- Se controla con `BANORTE_DEMO_TODAY=AAAA-MM-DD`; `scripts/start-all.cmd` la
  propaga a backend, servidor MCP y frontend.
- Los sellos de auditoría y los nombres de respaldo usan el reloj real a propósito;
  no son "hoy" para los datos.
- Prohibido `date.today()` fuera de `seed.reference_today()` y prohibido usar
  fechas literales en las pruebas: siempre derivadas de la referencia.

## 4. Dinero y capa de dominio

- El dinero se almacena y calcula en **centavos enteros** (`*_cents`).
- Los cálculos de dinero, porcentajes, cuotas y agregados viven en
  `money.py`, `finance.py`, `credit.py` o `domain.py`.
- Ninguna herramienta, pantalla o respuesta del modelo recalcula importes,
  porcentajes o saldos por su cuenta.
- Cada resultado declara su base (por ejemplo, "% del total de gastos del mes")
  y su periodo.

## 5. Separación de responsabilidades

- **Lectura:** libre, sin confirmación.
- **Cálculo:** determinista y en una herramienta propia; el modelo nunca hace
  aritmética con dinero ni porcentajes.
- **Escritura:** solo con confirmación de un evento de interfaz verificado en el
  servidor, atómica e idempotente.
- Un único punto de entrada por operación de dominio, compartido por REST, MCP
  y el agente. REST y MCP deben aceptar y rechazar exactamente lo mismo.

## 6. Herramientas MCP

- Cada herramienta tiene esquema de entrada estricto, validación, salida
  estructurada con unidades y base declarada, errores tipados y límite de tamaño.
- Devuelve `sin_dato` explícito y tipado cuando no hay información; nunca cero,
  vacío o `None` sin tipo.
- Descripción escrita para el modelo: cuándo usarla, cuándo no y qué devuelve,
  sin ejemplos de frases memorizables.

## 7. Seguridad y secretos

- Sin claves, credenciales ni PII en el repositorio, en la base de entrega ni en
  los registros. El frontend nunca recibe secretos.
- No se registran ni se envían al proveedor de IA datos que no sean necesarios.
- Las escrituras no mueven dinero real; el producto es una demostración.

## 8. Pruebas

- Cada herramienta nueva o corregida se prueba con entradas válidas, inválidas,
  en el límite, sin dato y retorno de `sin_dato`.
- Se prueba la uniformidad: la misma herramienta con entidades distintas
  devuelve el mismo tipo de respuesta.
- Se prueba la capa única: ningún módulo fuera del dominio recalcula importes o
  porcentajes.
- Se prueban idempotencia de escrituras y aislamiento de confirmación.
- La suite debe fallar antes del cambio y pasar después.

## 9. Cuota y alcance limitados

- Trabajo acotado a la tarea pedida; sin refactorizaciones ni archivos extra.
- Lecturas y comandos costosos se ejecutan una sola vez y se reutiliza la salida.
- Si una puerta falla, se detiene el trabajo y se reporta; no se avanza a ciegas.

## 10. Documentación y puertas de salida

- Actualizar `docs/PLAN.md` con el estado real y la evidencia de cada tarea.
- Toda puerta de salida exige suite en verde, compilación de producción y
  reconciliación `ok=true`, `failures=0`, sin regresiones.
- El trabajo se detiene y se espera aprobación en cada puerta indicada.

## 11. Entorno de pruebas en Windows

- Si `pytest` falla al preparar `pytest-of-<usuario>` con
  `PermissionError: [WinError 5] Acceso denegado`, el problema es del
  directorio temporal del sistema, no de la suite ni del código.
- Antes de ejecutar, redirigir `TEMP` y `TMP` a una carpeta escribible y fijar
  un `--basetemp` explícito:

  ```powershell
  $env:TEMP = "$env:LOCALAPPDATA\Temp\opencode"
  $env:TMP = $env:TEMP
  python -m pytest -q backend --basetemp="$env:TEMP\pytest-banorte"
  ```

- No se acepta este error como excusa para omitir pruebas: la puerta exige
  ejecutar la suite completa con la redirección aplicada.
