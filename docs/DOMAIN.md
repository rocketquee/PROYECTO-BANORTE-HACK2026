# DOMAIN.md — Modelo de dominio e invariantes
### Proyecto: `proyecto-banorte-ai-finanzas` · prototipo educativo · datos sintéticos · SQLite
### Estado: **especificación para aprobación** (documento normativo). Nada de lo aquí descrito está todavía aplicado al código ni a la base.
### Fecha: 2026-10-22 · Documentos relacionados: [AUDITORIA-FASE1.md](AUDITORIA-FASE1.md), [MIGRACION-FASE1.md](MIGRACION-FASE1.md)

---

## 0. Propósito y alcance

Este documento es la **única fuente de verdad de las definiciones financieras** del sistema. Define:

1. Las entidades y el **libro de movimientos** con tres tipos: `ingreso`, `gasto` y `transferencia`.
2. El significado exacto de cada magnitud mostrada (gasto, disponible, saldo total, balance del mes…).
3. Los **invariantes INV-1…INV-9**, con su interpretación operativa y **dónde se hacen cumplir** (restricción de base, capa única de dominio o reconciliación).
4. El contrato de la **función central de validación** y de la **capa única de métricas** (INV-9).

Regla de gobierno: **ninguna pantalla, herramienta MCP ni respuesta del asistente recalcula una métrica definida aquí.** Si un número no proviene de la capa de dominio, es un defecto.

Fuera de alcance de este documento (se especifican en Fases 2 y 3, pero sus principios se fijan en §9): interpretación de intención, validación conversacional de entradas y formato de respuesta.

---

## 1. Entidades

| Entidad | Tabla | Naturaleza | Notas |
|---|---|---|---|
| **Cuenta** | `accounts` | Lugar donde la persona tiene dinero disponible (`debit`, `savings`, …) | Tiene `balance` (saldo de la cuenta) y `currency` |
| **Meta de ahorro** | `savings_goals` | Objeto de ahorro con objetivo (`target_amount`) y ahorrado (`saved_amount`) | Tiene `deadline`, `status` |
| **Movimiento** | `transactions` | Unidad del **libro**: un evento que mueve dinero | Tres tipos (§2) |
| **Presupuesto** | `budgets` | Límite mensual por categoría | Define la **taxonomía de categorías de gasto** de la persona |
| **Tarjeta** | `cards` | Instrumento de crédito/débito | Informativa; no participa en el libro |
| **Registro de idempotencia** | `idempotency_records` | Evidencia de una escritura aplicada una sola vez | Clave → `action`, `request_hash`, `result_json` |

**Taxonomía de categorías.** Una *categoría* es una etiqueta de gasto. Las categorías legítimas son las declaradas en `budgets` (más las que la persona cree explícitamente). Una categoría que solo existe porque un movimiento mal tipado la introdujo (p. ej. `Ahorro` en el estado actual) **no es una categoría de gasto** y no debe aparecer en ninguna agregación de gasto.

---

## 2. El libro de movimientos

Todo movimiento tiene exactamente uno de **tres tipos**:

| Tipo | Semántica | Efecto sobre el dinero |
|---|---|---|
| `income` | **Ingreso**: dinero que entra desde fuera del patrimonio | Aumenta el saldo en cuentas |
| `expense` | **Gasto**: dinero que sale del patrimonio (consumo, pago) | Disminuye el saldo en cuentas |
| `transfer` | **Transferencia**: dinero que se mueve **entre cuentas propias y metas**, en cualquier sentido | **No cambia el patrimonio**; solo cambia dónde está |

### 2.1 Campos del movimiento

| Campo | `income` / `expense` | `transfer` |
|---|---|---|
| `date` | fecha del movimiento | fecha del movimiento |
| `description` | descripción legible | descripción legible |
| `amount` | **> 0** (el signo lo da el tipo) | **> 0** (el signo lo da `direction`) |
| `type` | `income` \| `expense` | `transfer` |
| `category` | **obligatoria** (categoría de gasto / `Ingresos`) | **NULL** (una transferencia no tiene categoría de gasto) |
| `account_id` | cuenta afectada | cuenta afectada (origen o destino según `direction`) |
| `goal_id` | **NULL** | **obligatoria**: meta involucrada |
| `direction` | **NULL** | `account_to_goal` (aportación) \| `goal_to_account` (retiro) |

### 2.2 Efectos exactos de una transferencia

Una transferencia de monto `M` produce **exactamente** estos efectos, ni uno más:

- `direction = account_to_goal` — aportación a una meta:
  - `accounts.balance` de la cuenta: **−M**
  - `savings_goals.saved_amount` de la meta: **+M**
  - **Nada más cambia.** Ni ingresos, ni gastos, ni categorías, ni balance del mes, ni anomalías, ni pagos fijos.
- `direction = goal_to_account` — retiro desde una meta:
  - `accounts.balance` de la cuenta: **+M**
  - `savings_goals.saved_amount` de la meta: **−M**
  - **Nada más cambia.**

---

## 3. Definiciones canónicas de las magnitudes

Estas definiciones **fijan** qué significa cada cifra que se muestra. Son la referencia de INV-6, INV-7 y INV-9.

| Magnitud | Definición exacta | Fuente |
|---|---|---|
| **Gasto del periodo** | `Σ amount` de movimientos con `type='expense'` en el periodo. **Nunca** incluye transferencias | `transactions` |
| **Ingreso del periodo** | `Σ amount` de movimientos con `type='income'` en el periodo | `transactions` |
| **Gasto por categoría** | `Σ amount` por `category` sobre movimientos `type='expense'` del periodo | `transactions` |
| **Balance del mes** | `ingreso del periodo − gasto del periodo` | derivado |
| **Saldo en cuentas** | `Σ accounts.balance` | `accounts` |
| **Ahorro en metas** | `Σ savings_goals.saved_amount` | `savings_goals` |
| **Saldo total** (patrimonio) | `saldo en cuentas + ahorro en metas` | derivado (INV-2) |
| **Disponible** | `saldo en cuentas` — es lo único que se puede mover a metas | derivado (INV-3) |
| **Falta para una meta** | `max(0, target_amount − saved_amount)` | derivado (INV-4) |
| **Progreso de una meta** | `100 · saved_amount / target_amount` — **base = objetivo de la meta** | derivado (INV-7) |
| **Porcentaje de una categoría** | `100 · gasto_categoría / gasto_total_del_periodo` — **base = gasto total del periodo** | derivado (INV-7) |
| **Porcentaje de presupuesto** | `100 · gasto_categoría / límite_categoría` — **base = límite de la categoría** | derivado (INV-7) |
| **Periodo en curso** | periodo que contiene la fecha de hoy: sus cifras están **incompletas** → tiempo verbal en presente | — |
| **Periodo cerrado** | periodo íntegramente anterior a hoy: sus cifras son **finales** → tiempo verbal en pasado | INV-8 |

**Base explícita (INV-7).** Todo porcentaje viaja acompañado de la base con la que se calculó. Texto y gráfica de una misma respuesta usan **la misma base**; la gráfica no puede tener su propio denominador.

---

## 4. Invariantes

### INV-1 — Una transferencia no altera nada salvo las dos posiciones que mueve
**Enunciado:** una transferencia **no** modifica ingresos, gastos, categorías, balance del mes, anomalías ni pagos fijos.
**Interpretación operativa:** toda agregación de gasto/ingreso/categoría/anomalía/duplicados/cobros fijos filtra por `type IN ('income','expense')` **por construcción** (no por lista negra que haya que recordar actualizar). El tipo `transfer` queda excluido de raíz.
**Se hace cumplir en:** capa única de dominio (§5) + `CHECK` de base (§6) + reconciliación (§10).
**Verificación:** tras cualquier secuencia de transferencias, `gasto`, `ingreso`, `gasto por categoría`, `balance del mes`, `anomalías` y `pagos fijos` son idénticos a los previos.

### INV-2 — Saldo total = cuentas + metas, y las transferencias no lo cambian
**Enunciado:** `saldo total = Σ accounts.balance + Σ savings_goals.saved_amount`. Una transferencia no cambia el saldo total.
**Interpretación operativa:** existe **una** función `total_balance(conn)` que suma ambas fuentes. Ninguna superficie suma solo cuentas.
**Se hace cumplir en:** capa única de dominio; reconciliación.
**Verificación:** por cada transferencia, `Δ saldo en cuentas + Δ ahorro en metas = 0`.

### INV-3 — Disponible = saldo en cuentas; cada transferencia lo ajusta exactamente por su monto
**Enunciado:** `disponible = Σ accounts.balance`. Una transferencia de monto `M` con `direction=account_to_goal` reduce el disponible exactamente en `M`; con `direction=goal_to_account` lo aumenta exactamente en `M`.
**Interpretación operativa:** `available_balance` es una función distinta de `total_balance` y **nunca** se confunden. El ajuste se aplica en la misma transacción que el movimiento y queda registrado en el libro.
**Se hace cumplir en:** capa única de dominio + `CHECK (balance >= 0)` y trigger de no-negatividad (§6); reconciliación.
**Verificación:** para cada transferencia, el delta observado del saldo de la cuenta destino/origen es exactamente `±M`.

### INV-4 — Cotas del ahorro y de la aportación
**Enunciado:** el `saved_amount` de una meta **nunca** es negativo ni excede su `target_amount`; una aportación **nunca** excede (a) lo que falta para el objetivo ni (b) el disponible.
**Interpretación operativa:** el ahorrado de una meta se modifica **únicamente** por transferencias (nunca por `saved_amount`/`add_amount` de escritura directa). El estado `completada` es **consecuencia** de alcanzar el objetivo, no un efecto colateral de una escritura sin límites.
**Se hace cumplir en:** triggers de `savings_goals` y del libro (§6) + validación central (§5).
**Verificación:** `0 ≤ saved_amount ≤ target_amount` para toda meta, en todo momento.

### INV-5 — Escritura atómica, idempotente y con confirmación verificada en servidor
**Enunciado:** toda escritura es (a) **atómica** (todo o nada), (b) **idempotente** (repetir la misma petición no vuelve a aplicar el efecto) y (c) exige una **confirmación originada en un evento de UI verificado en el servidor**.
**Interpretación operativa:**
- Atomicidad: `BEGIN IMMEDIATE` … `COMMIT`, con `rollback` ante cualquier error; nunca dos escrituras parciales visibles.
- Idempotencia: **obligatoria** para toda operación de escritura, con clave de idempotencia y `request_hash`; una clave reutilizada con datos distintos se rechaza; una clave repetida con los mismos datos devuelve el resultado previo sin re-aplicar.
- Confirmación: el servidor emite un **token de un solo uso** ligado a (acción, hash de parámetros, `trace_id`, caducidad); la confirmación se acepta **solo** si el token existe, no ha sido consumido y corresponde al mismo hash. No basta con un identificador provisto por el cliente ni con estado en memoria del proceso.
**Se hace cumplir en:** capa de escritura + `idempotency_records` (§7).
**Verificación:** dos confirmaciones simultáneas de la misma operación aplican **un solo** efecto; con la misma clave y los mismos datos, la segunda es un *replay*.

### INV-6 — Toda cifra proviene de una consulta
**Enunciado:** toda cifra mostrada proviene de una consulta a los datos. Si no hay dato, se **declara** claramente; **nunca** se estima ni se inventa.
**Interpretación operativa:** no se derivan afirmaciones del reloj (`date.today()`) ni de supuestos ("vas a mitad de la quincena") para describir un periodo consultado. Un periodo sin movimientos responde "no hay datos para ese periodo", no un resumen del mes en curso.
**Se hace cumplir en:** capa única de dominio + capa de composición de respuestas.

### INV-7 — Todo porcentaje declara su base, y texto y gráfica comparten la misma
**Enunciado:** todo porcentaje exhibe la base con la que se calculó; el texto y la gráfica de una misma respuesta usan la **misma** base.
**Interpretación operativa:** la base se calcula en la capa única de dominio y viaja con el dato; la composición de UI no introduce un denominador propio.
**Se hace cumplir en:** capa única de dominio + contrato de UI.

### INV-8 — Fechas y tiempo verbal
**Enunciado:** fechas inválidas, futuras o sin datos se **declaran**; nunca se reinterpretan en silencio. El tiempo verbal respeta el estado del periodo.
**Interpretación operativa:** un mes futuro no se convierte en "el año pasado"; una fecha límite en el pasado se rechaza; un periodo cerrado se narra en pasado y uno en curso en presente.
**Se hace cumplir en:** validación central (§5) + capa única de dominio (estado del periodo) + composición.

### INV-9 — Una sola capa de dominio
**Enunciado:** las métricas derivadas se calculan en **una única capa de dominio**. Ninguna pantalla, herramienta ni respuesta recalcula por su cuenta.
**Interpretación operativa:** existe **una** implementación por métrica (backend). La API REST, el servidor MCP y el asistente **llaman** a esa capa; el cliente **muestra** lo que recibe y no vuelve a sumar (`BudgetPlanner` deja de recalcular `total_spent`, `available` y `pct`). La validación de entradas también es única: API y MCP invocan la misma función central, sin límites contradictorios entre capas.
**Se hace cumplir en:** estructura del código + pruebas que fallan si aparece un segundo cálculo.

---

## 5. Capa única de dominio y validación central

**Ubicación propuesta** (misma capa de servicios, reutilizable por API y MCP):

- `backend/app/services/domain.py` — **autoridad de invariantes y validación**.
- `backend/app/services/finance.py` — **autoridad de métricas derivadas** (se conserva y se corrige, no se duplica).

Ambos módulos son *la* capa de dominio; ninguna otra parte del sistema calcula ni valida.

### 5.1 Contrato de la función central de validación

Una única puerta de entrada para toda entrada que toque el patrimonio:

```python
# domain.py  (borrador de contrato; los nombres de código se fijan al implementar)
class DomainError(ValueError):
    code: str          # código estable, p. ej. "amount_not_positive"
    message: str       # mensaje en español para la persona

def validate_amount(value, *, kind: str) -> float            # kind ∈ {"goal_target", "income", "expense", "transfer"}
def validate_money_range(value, *, lo, hi, label)
def validate_goal_name(name: str) -> str                     # unicidad + longitud + saneamiento
def validate_deadline(value: str | None) -> str | None       # ISO válida y no pasada
def validate_transfer(conn, *, goal_id: int, amount: float,
                      direction: str) -> None                # INV-3 e INV-4 (falta y disponible)
def period_state(year: int, month: int) -> str               # "en_curso" | "cerrado" | "futuro"
def assert_period_has_data(conn, year: int, month: int)      # INV-6 / INV-8
```

Reglas del contrato:

- **Una sola definición de cada regla.** Los límites de importe, la longitud del nombre y las reglas de fecha existen **una vez** aquí; API y MCP solo invocan.
- **Los errores son tipados** (código estable) y con mensaje para la persona; la UI puede traducir el código sin volver a decidir la regla.
- **La validación no estima.** Un periodo futuro o sin datos se **declara** (`period_state`, `assert_period_has_data`), no se sustituye por el mes en curso.
- **Trazabilidad:** toda escritura registra su `trace_id`; los registros no incluyen datos sensibles (ya implementado en `structured_logging.py`).

### 5.2 Declaración de la base de cada porcentaje

`finance.py` devuelve, junto a cada porcentaje, su base:

```python
{"category": "...", "amount": 1234.5, "pct": 12.3, "pct_base": "gasto_total_del_periodo", "pct_base_value": 10000.0}
{"goal": "...", "saved": 22500.0, "progress_pct": 50.0, "pct_base": "objetivo_de_la_meta", "pct_base_value": 45000.0}
```

Así el texto y la gráfica consumen la **misma** base (INV-7) y ninguna superficie la reinterpreta.

---

## 6. Restricciones en la base de datos

Además de la validación en la capa de dominio, el modelo se hace cumplir **físicamente**. DDL objetivo (SQLite; requiere reconstrucción de tabla, ver [MIGRACION-FASE1.md](MIGRACION-FASE1.md)):

```sql
-- Libro de movimientos: tres tipos, con la forma que exige cada uno.
CREATE TABLE transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    description TEXT    NOT NULL,
    amount      REAL    NOT NULL CHECK (amount > 0),
    type        TEXT    NOT NULL CHECK (type IN ('income','expense','transfer')),
    category    TEXT,
    account_id  INTEGER REFERENCES accounts(id),
    goal_id     INTEGER REFERENCES savings_goals(id),
    direction   TEXT,
    CHECK (
        (type IN ('income','expense')
            AND category IS NOT NULL AND account_id IS NOT NULL
            AND goal_id IS NULL AND direction IS NULL)
        OR
        (type = 'transfer'
            AND category IS NULL AND goal_id IS NOT NULL AND account_id IS NOT NULL
            AND direction IN ('account_to_goal','goal_to_account'))
    )
);

-- INV-4: el ahorrado de una meta nunca es negativo ni excede su objetivo.
CREATE TRIGGER trg_goal_saved_bounds_ins
BEFORE INSERT ON savings_goals
WHEN NEW.saved_amount < 0 OR NEW.saved_amount > NEW.target_amount
BEGIN SELECT RAISE(ABORT, 'INV-4: el ahorrado debe estar entre 0 y el objetivo de la meta'); END;

CREATE TRIGGER trg_goal_saved_bounds_upd
BEFORE UPDATE OF saved_amount, target_amount ON savings_goals
WHEN NEW.saved_amount < 0 OR NEW.saved_amount > NEW.target_amount
BEGIN SELECT RAISE(ABORT, 'INV-4: el ahorrado debe estar entre 0 y el objetivo de la meta'); END;

-- INV-4: una transferencia no puede dejar el ahorrado fuera de cotas.
CREATE TRIGGER trg_transfer_within_goal_bounds
BEFORE INSERT ON transactions
WHEN NEW.type = 'transfer'
BEGIN
  SELECT RAISE(ABORT, 'INV-4: la aportación supera lo que falta para la meta')
  WHERE NEW.direction = 'account_to_goal'
    AND (SELECT saved_amount FROM savings_goals WHERE id = NEW.goal_id) + NEW.amount
        > (SELECT target_amount FROM savings_goals WHERE id = NEW.goal_id);
  SELECT RAISE(ABORT, 'INV-4: el retiro supera lo ahorrado en la meta')
  WHERE NEW.direction = 'goal_to_account'
    AND (SELECT saved_amount FROM savings_goals WHERE id = NEW.goal_id) - NEW.amount < 0;
END;

-- INV-3: el disponible nunca es negativo.
CREATE TRIGGER trg_account_balance_non_negative
BEFORE UPDATE OF balance ON accounts
WHEN NEW.balance < 0
BEGIN SELECT RAISE(ABORT, 'INV-3: el saldo disponible no puede ser negativo'); END;
```

**Principio:** lo que hoy es una convención del código pasa a ser una **restricción del motor**. Un movimiento `transfer` mal formado, un ahorrado fuera de cotas o un saldo negativo **no pueden existir** en la base, sin importar qué capa escriba.

---

## 7. Escrituras

Toda operación de escritura (crear meta, editar meta, aportar a meta, fijar presupuesto) cumple INV-5:

1. **Atómica:** una sola transacción `BEGIN IMMEDIATE … COMMIT`; cualquier error → `rollback` completo (ya existe `db()` con commit/rollback, se conserva).
2. **Idempotente:** clave de idempotencia **obligatoria**, `request_hash = SHA-256(params normalizados)`; reutilizar la clave con otros datos se rechaza; repetir con los mismos datos devuelve el resultado guardado con `idempotent_replay: true`.
3. **Con confirmación verificada en servidor:** token de un solo uso emitido por el servidor, ligado a (acción, hash de parámetros, `trace_id`, caducidad). Se elimina la confirmación por `action_id` respaldada en estado en memoria del proceso.
4. **Con `trace_id`:** cada escritura emite un registro estructurado; nunca se registran datos sensibles.

**Un solo camino por operación.** `create_savings_goal`, `update_savings_goal` y `apply_savings_contribution` existen **una** vez, y son la única vía por la que cambian metas y saldos. La API REST y el servidor MCP son dos transportes del **mismo** caso de uso, no dos implementaciones.

---

## 8. Presentación de resultados

- **Formato según lo pedido:** si la persona pide un dato puntual, se responde con el dato; si pide un desglose, con tabla; si pide una comparación visual, con gráfica. No se sustituye un dato por una gráfica.
- **Primero lo preguntado, después el detalle.**
- **Coherencia:** el texto y la gráfica de una respuesta comparten la misma base y el mismo periodo (INV-7).
- **Base declarada:** todo porcentaje indica su base.
- **Tiempo verbal:** periodo cerrado → pasado; periodo en curso → presente (INV-8).
- **Sin dato → se declara:** "no hay datos para ese periodo / no tengo ese producto", nunca una cifra inventada (INV-6).

---

## 9. Principios de interpretación (norma de dominio; se implementan en Fase 2)

Se fijan aquí porque condicionan qué es un dato válido; su implementación corresponde a la Fase 2.

1. **Orden de resolución:** (1) **entidades conocidas** de la persona —metas y categorías existentes, por coincidencia aproximada—, (2) **intención**, (3) **palabras de alerta**.
2. **Alertas de seguridad con señales explícitas y de alta precisión:** una palabra aislada (`clave`, `token`, `nip`, `cvv`, `receta`, `partido`, `bolsa`…) **no** dispara por sí sola una respuesta de seguridad, de rechazo ni de fuera de alcance. Se exige coocurrencia y contexto.
3. **Un objeto nuevo solo se crea con un nombre declarado explícitamente** por la persona o confirmado en un formulario. **Nunca** se infiere el nombre de una pregunta.
4. **Si falta un dato necesario, se pregunta exactamente por ese dato, con opciones.** "No entendí" es el último recurso y debe indicar **qué sí se entendió**.
5. **Uniformidad:** toda capacidad (cuánto falta, cuánto llevo, proyección dado un ahorro periódico, aportación parcial —fracciones, "todo", montos—, recortes sobre gasto discrecional, comparación entre periodos y entre categorías) funciona para **todas** las metas y categorías existentes, con tolerancia a errores de escritura y lenguaje coloquial.

---

## 10. Reconciliación

Un **script de reconciliación** verifica los invariantes sobre la base real y **falla con detalle por invariante y por fila**. Identidades comprobables:

| ID | Comprobación |
|---|---|
| INV-1 | Ninguna fila con `type='transfer'` aparece en agregaciones de gasto/ingreso/categoría/anomalía/cobro fijo. No existe ninguna fila con `type='expense'` cuya categoría no sea de la taxonomía declarada. |
| INV-2 | `Σ accounts.balance + Σ savings_goals.saved_amount` es consistente; por cada transferencia `Δ cuentas + Δ metas = 0`. |
| INV-3 | Por cada transferencia, el ajuste de la cuenta es exactamente `±amount`; ningún `balance < 0`. |
| INV-4 | `0 ≤ saved_amount ≤ target_amount` y `saved_amount ≤ target_amount` en todo momento; ninguna transferencia deja la meta fuera de cotas. |
| INV-5 | Todo cambio de meta tiene un registro de idempotencia correspondiente; no hay efectos duplicados. |

El script se ejecuta sobre la **base real** y sobre una **base recién sembrada**, y es parte de la definición de terminado.

---

## 11. Glosario rápido

| Término | Significado en este sistema |
|---|---|
| **Movimiento** | Unidad del libro (`ingreso`, `gasto` o `transferencia`) |
| **Transferencia** | Movimiento entre una cuenta propia y una meta, en cualquier sentido; no altera el patrimonio |
| **Gasto** | Consumo que sale del patrimonio; único tipo que alimenta categorías, anomalías y pagos fijos |
| **Disponible** | Saldo en cuentas; lo único que se puede mover a metas |
| **Saldo total** | Saldo en cuentas + ahorro en metas (patrimonio) |
| **Ahorro en metas** | Suma del `saved_amount` de todas las metas |
| **Balance del mes** | Ingresos del mes − gastos del mes |
| **Base de un porcentaje** | Denominador con el que se calculó; se declara siempre |
| **Periodo en curso / cerrado** | Contiene hoy / es íntegramente anterior a hoy |
| **Reconciliación** | Verificación automática de INV-1…INV-4 sobre los datos reales |

---

### Declaración de estado
Este documento es **especificación**. No se ha modificado ningún archivo de código ni la base de datos. El diseño concreto de la migración que llevará los datos actuales a este modelo está en [MIGRACION-FASE1.md](MIGRACION-FASE1.md) y **también requiere tu aprobación antes de ejecutarse**.
