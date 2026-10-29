# MIGRACION-FASE1.md — Diseño de migración y reparación del libro
### Proyecto: `proyecto-banorte-ai-finanzas` · base afectada: `backend/data/banorte.db`
### Estado: **diseño para aprobación** — **la base NO se ha tocado**
### Fecha: 2026-10-22 · Depende de: [DOMAIN.md](DOMAIN.md) · Contexto: [AUDITORIA-FASE1.md](AUDITORIA-FASE1.md)

---

## 0. Resumen

La base real contiene **exactamente una fila mal clasificada** y ningún otro defecto de integridad (ver §1). La migración hace dos cosas y solo dos:

1. **Reforma el esquema** del libro para admitir el tercer tipo (`transfer`) y hacer invariables por restricción de motor lo que hoy es convención (INV-1, INV-3, INV-4).
2. **Reclasifica la fila mal tipada** como transferencia, reparando con ello todas las métricas derivadas (gastos, categorías, balance del mes) **sin tocar saldos ni ahorros**, que ya eran correctos.

Es **idempotente** (ejecutarla dos veces no cambia nada), **atómica**, **con copia de seguridad previa obligatoria** y **reversible**.

---

## 1. Estado verificado de la base (evidencia, solo lectura)

Medición del 2026-10-22 sobre `backend/data/banorte.db` (155,648 bytes):

```
transactions DDL:
  type TEXT NOT NULL CHECK (type IN ('income','expense'))      ← 'transfer' prohibido por el motor

Filas mal clasificadas (type='expense' con categoría fuera de la taxonomía declarada en budgets):
  id=967 · 2026-10-22 · "Abono a meta: Compra planeada" · 22500.0 · expense · "Ahorro" · account_id=2
  → exactamente 1 fila

Cuentas: Nómina 24,580.35 · Ahorro 35,700.00 · Digital 3,140.80   ·  Σ = 63,421.15
Metas:   Fondo de emergencia 18,500 · Viaje a Japón 8,200 · Compra planeada 22,500  ·  Σ = 49,200.00
Ahorro en metas: 49,200.00          Σ cuentas + Σ metas = 112,621.15

Escaneos de integridad (todos limpios):
  amount <= 0 ................ 0 filas
  type inválido .............. 0 filas        account_id NULL ......... 0 filas
  account_id huérfano ........ 0 filas        goals saved < 0 ......... 0 filas
  goals saved > target ....... 0 filas        accounts balance < 0 .... 0 filas
  periodos: 2025-11 … 2026-10 (12 meses completos)
```

**Vínculo estructural con la meta (sin usar el texto del movimiento).** El registro de idempotencia de la aportación declara la operación:

```
idempotency_records
  ea4794db-1095-4284-b2ff-2500f7e8e49a | apply_savings_contribution | 2026-10-23 01:22:41
    result_json → goal.id = 3, amount = 22500.0, available_balance = 63421.15
  dc885590-6f2d-4f74-b6eb-9d2a76ce707f | create_savings_goal | 2026-10-22 21:01:00
    result_json → goal.id = 3, saved_amount = 0.0
```

De ahí se obtiene el par **(monto = 22,500.00, meta = 3)**. La única fila del libro que casa con ese par es `id=967`. La meta 3 pasó de `0` a `22,500` (delta = +22,500) y la cuenta 2 pasó de 58,200.00 a 35,700.00 (delta = −22,500): **la misma cantidad en ambos lados**. La fila es, con certeza estructural, la aportación registrada como gasto.

---

## 2. Regla de detección (general, no basada en texto)

La clasificación **no** mira descripciones ni programará contra frases de pruebas. Se basa en **estructura y relaciones**:

```
PASO 1 — Taxonomía declarada
  T = { category FROM budgets }              # categorías de gasto que la persona declaró
  (las filas type='income' usan la categoría de ingreso; no participan)

PASO 2 — Candidatos (movimientos de gasto con categoría inexistente en la taxonomía)
  C = { t : t.type='expense' AND t.category NOT IN T }

PASO 3 — Corroboración por vínculo con una meta
  P = { (goal_id, monto) } extraído de idempotency_records
        con action ∈ {'apply_savings_contribution','update_savings_goal'}
  Para cada t ∈ C:
      si ∃ (goal_id, t.amount) ∈ P  y  la meta goal_id tiene saved_amount ≥ t.amount
      → CLASIFICADA como transferencia (direction='account_to_goal', goal_id)
      si no
      → NO CLASIFICABLE  → se REPORTA y NO se modifica
```

**Resultado sobre la base real:** `C` tiene 1 fila (id 967); se corrobora con el par `(goal_id=3, 22500.0)`; **0 filas no clasificables**.

Se aplica el mismo algoritmo a filas `income` de origen dudoso en sentido inverso (`goal_to_account`) con `action ∈ {'withdraw'}` si existiera; **hoy no hay ninguna**.

---

## 3. Esquema objetivo

Se aplica el DDL de [DOMAIN.md §6](DOMAIN.md): `type ∈ ('income','expense','transfer')`, `CHECK` de forma por tipo, `amount > 0`, y los cuatro triggers de INV-3/INV-4. En SQLite un `CHECK` no puede alterarse, por lo que se usa **reconstrucción de tabla** (procedimiento de 12 pasos) dentro de una transacción.

---

## 4. Procedimiento (paso a paso)

```
PASO 0 — Precondiciones y copia de seguridad (obligatoria)
  a. Verificar que el archivo existe y que no hay otra migración en curso.
  b. Copiar  backend/data/banorte.db  →  backend/data/banorte.db.bak-<YYYYMMDD-HHMMSS>
     · Si ya existe una copia con esa marca de tiempo, no se sobreescribe: se aborta con aviso.
  c. Calcular y registrar el SHA-256 del original y de la copia; deben coincidir.
  d. Abrir SIEMPRE en modo lectura para el diagnóstico; solo el paso 2 escribe.

PASO 1 — Idempotencia (guarda de ejecución única)
  clave = 'migration:phase1:ledger-v1'   (determinista)
  Si idempotency_records ya contiene esa clave
     → la migración NO hace nada, devuelve el resultado previo y sale (replay).

PASO 2 — Transacción única
  BEGIN IMMEDIATE
    1. CREATE TABLE transactions_new (…DDL objetivo…)
    2. Crear triggers de INV-3/INV-4 (los de savings_goals y accounts son independientes de la tabla)
    3. Copiar filas:
         · type IN ('income','expense') y NO candidata  → columnas tal cual,
             goal_id = NULL, direction = NULL
         · candidata corroborada                         → type='transfer',
             category=NULL, goal_id=<meta>, direction='account_to_goal'
         · candidata NO corroborada                      → NO se copia aquí:
             se registra en el informe y se conserva sin cambios (ver §6)
    4. DROP TABLE transactions ; ALTER TABLE transactions_new RENAME TO transactions
    5. Recrear índices idx_tx_date, idx_tx_category
    6. INSERT en idempotency_records la clave de migración con
         action='migrate_ledger_v1', request_hash=<hash del plan>,
         result_json={rows: [...], transfer_ids: [...], unclassified: [...], checksum: '<sha256>'}
    7. Ejecutar las comprobaciones de §5 dentro de la misma transacción
  COMMIT   (si cualquier paso o comprobación falla → ROLLBACK y la base queda intacta)
```

---

## 5. Comprobaciones dentro de la transacción (antes del `COMMIT`)

| # | Comprobación | Criterio |
|---|---|---|
| 1 | Conteo de filas | `COUNT(*)` nuevo = `COUNT(*)` original |
| 2 | Σ amount por tipo | `Σ expense` nuevo = `Σ expense` original − 22,500.00; `Σ income` igual; aparece exactamente `Σ transfer = 22,500.00` |
| 3 | INV-1 | Ninguna fila `transfer` con `category` distinta de NULL; ninguna fila `expense` con categoría fuera de la taxonomía |
| 4 | INV-2 | `Σ accounts.balance + Σ savings_goals.saved_amount` = **112,621.15** (idéntico al valor previo a la operación) |
| 5 | INV-3 | `Σ accounts.balance` = **63,421.15** (sin cambios); por la transferencia, `Δ cuenta = −22,500.00` |
| 6 | INV-4 | `0 ≤ saved_amount ≤ target_amount` para las 3 metas |
| 7 | Integridad referencial | `goal_id` de la transferencia existe; `account_id` existe |
| 8 | No duplicados | Ninguna fila repetida por `(date, description, amount, type)` inesperadamente |

Si las 8 pasan → `COMMIT`; si alguna falla → `ROLLBACK` y se restaura la copia de seguridad.

---

## 6. Filas no clasificables

Se **reportan y no se modifican**, con `id`, `date`, `type`, `category`, `amount`, `account_id` y el motivo (`sin vínculo con meta en idempotency_records`).

**Estado real: cero filas no clasificables.** El procedimiento queda preparado para reportarlas si aparecieran.

---

## 7. Efecto esperado sobre los datos (antes → después)

| Magnitud | Antes | Después | Cambio |
|---|---|---|---|
| Fila `id=967` | `expense` · categoría `Ahorro` | `transfer` · `category=NULL` · `goal_id=3` · `account_to_goal` | reclasificada |
| Gasto del periodo **2026-10** | 42,131.93 | **19,631.93** | −22,500.00 |
| Ingreso del periodo 2026-10 | 10,959.27 | 10,959.27 | sin cambios |
| Balance del mes 2026-10 | −31,172.66 | **−8,672.66** | corregido |
| Categoría `Ahorro` en gastos | 22,500.00 (53.4% del gasto del mes) | **no existe** | eliminada |
| Σ cuentas (disponible, INV-3) | 63,421.15 | 63,421.15 | **sin cambios** (el débito era correcto) |
| Σ ahorro en metas | 49,200.00 | 49,200.00 | sin cambios |
| **Saldo total** (INV-2) | 112,621.15 | 112,621.15 | **conservado** |
| `budgets` (taxonomía) | — | — | sin cambios (la categoría falsa desaparece por sí sola) |
| Movimientos totales | 967 | 967 | sin cambios |

**Ningún saldo de cuenta ni ahorro de meta se modifica.** La reparación es exclusivamente de **clasificación**; los importes ya eran correctos.

---

## 8. Reversión

- **Transacción:** cualquier fallo antes del `COMMIT` deja la base intacta.
- **Copia de seguridad:** `backend/data/banorte.db.bak-<marca>` permite restaurar el estado exacto anterior.
- **Idempotencia:** reintentar la migración no re-aplica nada; para repetirla tras una reversión, debe eliminarse la clave `migration:phase1:ledger-v1` (acción explícita y registrada).

---

## 9. Idempotencia de la migración

- Clave determinista `migration:phase1:ledger-v1`: la segunda ejecución detecta la clave y no escribe.
- El filtro del PASO 1 excluye filas que ya son `transfer`, por lo que la transformación es estable ante repetición.
- `request_hash` = hash del plan de migración: si el plan cambia y la clave ya existe, la migración se **rechaza** en lugar de aplicar un plan distinto.

---

## 10. Qué NO hace esta migración (y por qué es correcto)

- **No recalcula saldos de cuentas ni ahorros de metas:** el débito ya era correcto (INV-3) y el ahorrado de la meta ya era correcto (INV-4). Solo cambia la clasificación.
- **No toca `budgets`:** la categoría `Ahorro` desaparece de las agregaciones al dejar de ser un gasto; no había un presupuesto declarado para ella.
- **No reescribe descripciones ni textos:** la detección es estructural.
- **No corrige las Clases B–E:** pertenecen a las Fases 2 y 3.
- **No resuelve A-9** (que los saldos se deriven del libro) más allá de lo que exigen INV-2/INV-3 literalmente: los saldos de apertura de la demo siguen siendo un dato de partida declarado, y la reconciliación verifica conservación y ajuste exacto, no la derivación completa. Si quieres derivación completa, es una decisión aparte (ver §11).

---

## 11. Decisiones pendientes antes de ejecutar

1. **Aprobar [DOMAIN.md](DOMAIN.md)** (definiciones, INV-1…INV-9, restricciones de base).
2. **Aprobar este diseño de migración** (reclasificar 1 fila + reconstruir la tabla del libro).
3. **Modelo de saldos (A-9):**
   - **(a)** Mantener los saldos como dato de partida declarado y reconciliar conservación y ajuste exacto (INV-2/INV-3 tal como están enunciados). **Alcance actual.**
   - **(b)** Derivar por completo los saldos del libro (saldo de apertura + movimientos), lo que exige sembrar un saldo de apertura que cuadre con los 12 meses de la demo. Cambia las cifras mostradas de la demo.
4. **Ejecutar la Fase 1 completa en un solo tramo** (pasos 1–7 del plan de [AUDITORIA-FASE1.md §9](AUDITORIA-FASE1.md)) o revisar cada artefacto antes de aplicarlo.

---

### Declaración de estado
**No se ha modificado la base de datos ni ningún archivo de código.** Todo lo anterior es diseño verificado contra datos reales en modo solo lectura. La migración se ejecuta únicamente tras tu aprobación explícita de este documento y de [DOMAIN.md](DOMAIN.md).
