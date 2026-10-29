# Diseño: base de datos a nivel plataforma bancaria

### Proyecto: `proyecto-banorte-ai-finanzas` · Datos exclusivamente sintéticos · Repositorio público
### Estado: **propuesta para aprobación — la base no se ha modificado**
### Referencias: `docs/DOMAIN.md` (INV-1…INV-9), `docs/MIGRACION-FASE1.md`, `docs/AUDITORIA-FASE1-2026-10-25.md`

---

## 1. Auditoría del estado actual (línea base medida)

Medido sobre una base temporal con `BANORTE_DEMO_TODAY=2026-10-25` (no toca `banorte.db`):

```
seed_seconds = 2.255
db_kb        = 156.0
tables       = accounts, budgets, cards, idempotency_records, savings_goals, transactions
indexes      = idx_tx_date, idx_tx_category
transactions = 984        date_range = 2025-11-01 → 2026-10-25   (12 meses)
  accounts 3 · cards 2 · savings_goals 3 · budgets 12 · idempotency_records 0
```

### 1.1 Representación del dinero — **punto que requiere tu decisión (§2)**

Todo el dinero es **coma flotante** (`REAL`):

| Dónde | Evidencia |
|---|---|
| `transactions.amount REAL NOT NULL` | `seed.py:22` |
| `accounts.balance REAL` | `seed.py:50` |
| `cards.balance` / `credit_limit REAL` | `seed.py:58-59` |
| `savings_goals.target_amount` / `saved_amount REAL` | `seed.py:66-67` |
| `budgets.monthly_limit REAL` | `seed.py:83` |

El síntoma está en la propia migración: compara con **tolerancia**

```38:38:backend/app/core/migrate.py
EPS = 0.011
```

y las verificaciones hacen `abs(a - b) > EPS` en vez de igualdad exacta (`migrate.py:250-260`, `279-286`). Eso es exactamente el defecto que los enteros en centavos eliminan: se compara por igualdad, sin epsilon. Además, `finance.py` aplica `round(..., 2)` en cada escritura para contener el error — parches dispersos que no son una garantía contable.

### 1.2 Esquema, integridad y calidad

Lo que **sí** hay: llaves foráneas declaradas (`transactions.account_id`/`goal_id REFERENCES`), `PRAGMA foreign_keys = ON` en cada conexión (`database.py:15`, `migrate.py:62`), `CHECK (amount > 0)`, `CHECK (type IN ('income','expense','transfer'))`, `UNIQUE` en `budgets.category`, 4 triggers de invariantes (INV-1, INV-3, INV-4), `savings_goals.created_at`.

Lo que **falta** respecto al objetivo:

| Hueco | Evidencia |
|---|---|
| Sin tabla de perfil ni preferencias | no existe la tabla |
| 6 tablas de dominio y solo 2 índices | medido arriba |
| `created_at`/`updated_at` solo en `savings_goals` e `idempotency_records` | `seed.py:70,78` |
| Sin bitácora de auditoría de escrituras | no existe |
| Sin tabla de versiones de esquema | la versión vive como **fila** en `idempotency_records` con clave `migration:phase1:ledger-v1` (`migrate.py:34`) |
| Categorías y comercios son literales del código | `SPEND_CATALOG` (`seed.py:132-147`), `DEFAULT_BUDGETS` (`seed.py:164-177`) |
| Sin marcado de casos de calidad de datos | el cobro duplicado y el cargo atípico existen (`seed.py:277-282`) pero **no están etiquetados** |

### 1.3 Migraciones

`migrate.py` es una migración **única y hard-coded** de la Fase 1: idempotente por clave, atómica (`BEGIN IMMEDIATE`), con **respaldo obligatorio previo** (`backup()`), 8 comprobaciones antes del `COMMIT` (`_verify`) y `PRAGMA foreign_key_check`. Son buenos cimientos, pero:

- **No hay registro versionado**: cada migración nueva añadiría otra clave en `idempotency_records`; no se puede saber "en qué versión está" la base de un vistazo.
- **No corre al iniciar**: `ensure_db()` solo llama `seed.init_db()` (`database.py:32-40`); `migrate.migrate()` es solo CLI (`migrate.py:426`).

### 1.4 Semilla: determinismo y volumen

- Es determinista en la **secuencia** (`random.Random(42)`, `seed.py:223`) pero **no en el calendario**: por defecto usa `date.today()` (`seed.py:203-214`). Sin `BANORTE_DEMO_TODAY`, dos máquinas producen bases distintas. Hoy no hay prueba de determinismo.
- **12 meses**, no 24: `_month_add(today.year, today.month, -11)` (`seed.py:225`).
- 984 movimientos: volumen de juguete para el objetivo.
- `accounts.balance` es un **fixture estático** (24,580.35 / 58,200 / 3,140.80) que ninguna escritura deriva del libro: ya identificado como A-9 y como la razón de que hoy **no haya reconciliación posible** (`docs/AUDITORIA-FASE1.md:94`).
- **Tensión de INV-4 en la propia semilla**: dos metas escriben el ahorrado a mano en el `INSERT` (18,500 y 8,200, `seed.py:308-313`) mientras la tercera lo hace por transferencia (`seed.py:317-322`). Con la disciplina que fijamos en el Tramo A, el ahorrado **solo** cambia por transferencias: la semilla nueva debe fondear las tres por transferencia.

### 1.5 Reconciliación

No existe. `docs/DOMAIN.md:306-335` la especifica; `docs/AUDITORIA-FASE1-2026-10-25.md:61` confirma su ausencia.

---

## 2. Decisión 1 (bloqueante): dinero en centavos

### Opciones

| | **A. Enteros en centavos** | **B. `REAL` + redondeo disciplinado** |
|---|---|---|
| Tipo | `amount_cents INTEGER NOT NULL` | `REAL` + `round()` en cada escritura |
| Comparación | **igualdad exacta** (sin `EPS`) | tolerancia (hoy `EPS = 0.011`) |
| INV-2/INV-3/INV-4 | verificables con `SUM(cents)` exacto | pueden fallar por 1 centavo acumulado |
| Riesgo | migración de datos y de contrato (una vez) | deuda permanente: cada comparación nueva necesita epsilon |
| Tamaño | igual o menor (entero vs float en SQLite) | igual |
| Coste | alto, pero acotado y verificable | bajo ahora, creciente |

### Recomendación: **A**

El dinero nunca debe ser coma flotante. Con centavos, la reconciliación de INV-1…INV-4 se vuelve una **identidad aritmética exacta** y se elimina `EPS` y todos los `round()` defensivos. Es el cambio de mayor valor estructural de todo el encargo y el único que conviene hacer **antes** de multiplicar el volumen por diez.

### Cómo, sin romper lo que hoy funciona

1. **Base**: columnas `*_cents INTEGER NOT NULL`. Se renombran (no se reusan) para que ninguna consulta vieja lea centavos creyendo pesos.
2. **Frontera (clave del diseño)**: la conversión ocurre en **un solo módulo** `app/core/money.py`:
   - `to_cents("1234.56") -> 123456`, `to_pesos(123456) -> Decimal("1234.56")`.
   - La **API y el contrato de la interfaz no cambian**: siguen hablando en pesos con 2 decimales (`amount: number`). Así el frontend y `schema_version: "1.0"` quedan intactos.
   - Se usa `Decimal` (no `float`) al convertir, y `ROUND_HALF_UP` explícito en el único punto que redondea.
3. **Migración** `ledger-v2`: convierte cada `REAL` a centavos con `Decimal(str(x)).quantize(0.01)` y **verifica** que `Σ centavos` reconstruye `Σ pesos` dentro de 1 centavo por fila; con respaldo y transacción, igual que `ledger-v1`. Registrada en la tabla de versiones (§3).
4. **Pruebas**: se reescriben las que dependen de cifras fijas para derivar de la base (§8).

**Si prefieres B**, el diseño sigue siendo válido salvo §2.1-§2.3; simplemente se conserva `EPS` y se documenta como deuda explícita.

---

## 3. Decisión 2: versionado de migraciones

Sustituir la clave en `idempotency_records` por una tabla propia:

```sql
CREATE TABLE schema_migrations (
  version       TEXT PRIMARY KEY,          -- 'ledger-v2', 'platform-v1', ...
  applied_at    TEXT NOT NULL DEFAULT (datetime('now')),
  checksum      TEXT NOT NULL,             -- hash del plan aplicado
  result_json   TEXT NOT NULL,
  backup_file   TEXT
);
```

- El runner (`app/core/migrations/runner.py`) descubre migraciones en orden, aplica las pendientes **en una transacción cada una**, con **respaldo previo** y `PRAGMA foreign_key_check` antes del `COMMIT`.
- **Idempotente**: reejecutar no hace nada; con `checksum` distinto para la misma versión, aborta con explicación.
- **Corre al iniciar**: `ensure_db()` pasa a `ensure_database()` → crea carpetas → aplica migraciones pendientes → siembra **solo si** la base está vacía.
- La semilla nueva entra **como migración** (`platform-v1`), de modo que una base existente se enriquece sin perder datos.

---

## 4. Decisión 3: perfiles de demostración

Tres personas ficticias con situaciones y experiencia digital distintas, **seleccionables solo en modo demo**. Dos formas:

| | **A. Un archivo por perfil** | **B. `profiles` + `profile_id` en todo** |
|---|---|---|
| Cambio de perfil | reabrir otra base | filtrar por `profile_id` |
| Consultas | sin cambios | **toda** consulta debe acotar por perfil (riesgo de fuga cruzada) |
| Reconciliación | por base | sobre toda la base |
| Pruebas "nada funciona solo con un perfil" | comparar bases | comparar filas |

### Recomendación: **B**, con una guarda

Un solo archivo con `profiles(id, ...)` y `profile_id INTEGER NOT NULL REFERENCES profiles(id)` en cada tabla de dominio, para que el cambio de perfil sea un parámetro de contexto y no un reinicio. Guarda obligatoria: la capa de dominio recibe `profile_id` **siempre** y las pruebas de seguridad verifican que **ninguna** consulta devuelve filas de otro perfil. Si prefieres evitarlo, **A** es más simple y también cumple; la diferencia es dónde vive el aislamiento.

---

## 5. Esquema propuesto (normalizado, con integridad y auditoría)

Todas las tablas de dominio llevan `profile_id`, `created_at`, `updated_at`, y las claves foráneas activas.

| Área | Tablas | Notas de integridad |
|---|---|---|
| Perfil | `profiles`, `profile_preferences` | idioma, accesibilidad, canales, nivel digital; `CHECK` de valores permitidos |
| Cuentas | `accounts`, `account_balance_history` | historial de saldos por fecha (`UNIQUE(account_id, as_of)`) |
| Tarjetas | `cards`, `card_statements`, `card_statement_lines` | `closing_day`/`due_day` con `CHECK 1..28`; pago mínimo y periodo; folio `UNIQUE` |
| Crédito | `credit_products`, `credit_amortization`, `credit_payments` | `UNIQUE(product_id, installment_no)`; saldo derivado |
| Inversiones | `investment_instruments`, `investment_positions`, `investment_movements` | precio, unidades, `CHECK units > 0` |
| Seguros | `insurance_policies`, `insurance_coverages`, `insurance_premiums`, `insurance_claims` | prima y siniestro con `CHECK amount > 0` |
| Catálogo | `merchants`, `categories`, `subcategories` | jerarquía con `parent_id` autorreferente; `UNIQUE(name, parent_id)` |
| Recurrentes | `recurring_payments`, `beneficiaries` | periodicidad con `CHECK`; beneficiario con `CLABE` **enmascarada** |
| Presupuestos | `budgets`, `budget_history` | `UNIQUE(profile_id, category_id, period)` |
| Metas | `savings_goals`, `goal_contributions` | historial de aportaciones; **siempre** por transferencia (INV-4) |
| Avisos | `notifications`, `alerts` | sin datos sensibles |
| Ayuda | `help_topics` | catálogo de educación financiera |
| Estados de cuenta | `statements` | folio `UNIQUE`, periodo, resumen |
| Contexto | `fx_rates`, `calendars`, `calendar_days` | festivos y días hábiles para nómina y corte |
| Auditoría | `audit_log` | quién, qué, cuándo, `trace_id`, resultado; **sin** datos sensibles |
| Fixtures | `fixture_cases` | marca los casos de calidad de datos (§6.3) |
| Migraciones | `schema_migrations` | §3 |

**Índices** para las consultas frecuentes: `transactions(profile_id, date)`, `transactions(profile_id, category_id)`, `transactions(profile_id, type)`, `card_statements(card_id, period)`, `goal_contributions(goal_id, date)`, `budget_history(profile_id, period)`, `notifications(profile_id, read_at)`.

**FK activas**: con `PRAGMA foreign_keys = ON` por conexión (ya existe) y verificación `PRAGMA foreign_key_check` en cada migración.

---

## 6. Semilla

### 6.1 Determinismo

- Una única fuente de azar: `random.Random(SEED)` con `SEED = 20260101` y **fecha de referencia obligatoria** en la ruta de siembra (`BANORTE_DEMO_TODAY`, por defecto una constante congelada, no `date.today()`).
- Sin dependencia del reloj ni del entorno: la misma semilla y la misma fecha ⇒ **base bit a bit comparable** por suma de verificación del contenido (hash por tabla ordenada).
- **Prueba de determinismo**: dos siembras ⇒ mismo hash.

### 6.2 Historial y realismo

- **24 meses** exactos, con estacionalidad (diciembre, aguinaldo, vacaciones de verano, regreso a clases) y variación realista.
- Mezcla exigida: ingreso periódico (nómina), ingreso extraordinario (aguinaldo, bono, venta), pago fijo, gasto variable y gasto atípico.
- **Volumen objetivo**: miles de movimientos repartidos entre perfiles. Presupuesto: **siembra < 5 s** (hoy 2.25 s con 984 filas; el salto de volumen exige medir y, si hace falta, sembrar con `executemany` por lote e índices creados **después** de insertar).

### 6.3 Casos de calidad de datos — `fixture_cases`

Cada caso se **etiqueta** para que las pruebas lo localicen **sin codificar valores**:

```sql
CREATE TABLE fixture_cases (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kind        TEXT NOT NULL,     -- 'duplicado','atipico','mes_vacio','categoria_unica','nombre_similar'
  entity      TEXT NOT NULL,     -- 'transactions','merchants',...
  entity_id   INTEGER,
  period      TEXT,
  note        TEXT NOT NULL
);
```

Casos a sembrar: cobros duplicados, cargos atípicos, **meses sin datos**, categorías con un solo movimiento y entidades con nombres muy similares. La prueba consulta `fixture_cases` y luego los datos: **el vínculo es la tabla, no un valor escrito a mano**.

### 6.4 Perfiles

Tres personas ficticias con etapa de vida y experiencia digital distintas. Datos **exclusivamente sintéticos**:

- Nombres de catálogos ficticios; correos en dominio reservado de pruebas; teléfonos y documentos con formato **claramente inválido**; de tarjetas y cuentas, **solo últimos 4 dígitos**.
- Un `CHECK`/validador de la capa de datos rechaza cualquier valor que parezca real (p. ej. longitud de tarjeta completa) — así el propio esquema protege el repositorio público.

---

## 7. Invariantes con las entidades nuevas

INV-1…INV-9 se amplían: cada invariante declara en qué **tablas nuevas** aplica y cómo se verifica. La reconciliación (§1.5, hoy inexistente) pasa a recorrer **toda** la base y falla con detalle por invariante **y por fila**. Con centavos (§2), las identidades son exactas.

---

## 8. Plan de pruebas

| Grupo | Qué verifica |
|---|---|
| Esquema | FK activas; `CHECK`/`UNIQUE`/`NOT NULL` rechazan datos inválidos; FK rotas detectadas |
| Migración | idempotencia (reejecutar no cambia nada); base **con datos** se enriquece sin pérdida; base **vacía** se crea correcta; respaldo presente |
| Determinismo | dos siembras ⇒ **mismo hash de contenido** |
| Reconciliación | INV-1…INV-4 (y ampliadas) sobre toda la base, con las entidades nuevas |
| Rendimiento | siembra < 5 s y umbral por consulta principal, con volúmenes registrados |
| Aislamiento | ninguna consulta devuelve filas de otro perfil |
| Suite existente | **255 pruebas siguen en verde**; las que dependían de cifras fijas se reescriben para **derivar de la base**, y se **listan por separado** |

---

## 9. Ejecución por tramos (deteniéndome en cada uno)

| Tramo | Contenido | Puerta |
|---|---|---|
| **D0** | Este diseño + decisión de centavos | **Tu aprobación** |
| **D1** | `money.py`, migración `ledger-v2` a centavos, `schema_migrations`, runner al iniciar | Suite verde + reconciliación exacta |
| **D2** | Esquema de plataforma (§5) + migración `platform-v1` | Suite verde + FK/CHECK probados |
| **D3** | Semilla de 24 meses, fixtures etiquetados, 3 perfiles, determinismo y < 5 s | Determinismo + rendimiento |
| **D4** | Reconciliación de toda la base + pruebas de propiedades y ampliación de INV | Reconciliación verde |
| **D5** | `docs/DATA-DICTIONARY.md` (tabla/columna, reglas, ER en Mermaid) + cómo regenerar y cambiar la semilla | Revisión de docs |

---

## 10. Lo que necesito de ti para arrancar D1

1. **Dinero: ¿A (centavos) o B (float disciplinado)?** Recomiendo **A**. Es el único cambio que conviene antes de multiplicar el volumen, y elimina `EPS` y los `round()` defensivos.
2. **Perfiles: ¿A (un archivo por perfil) o B (`profile_id` en todo)?** Recomiendo **B**, con la guarda de aislamiento.
3. **Saldos: ¿derivados del libro (cierra A-9) o declarados y reconciliados por conservación?** El enriquecimiento hace insostenible el fixture estático actual; recomiendo **derivar** el disponible del libro y que la semilla abra con una transferencia de fondeo explícita.
4. **Volumen**: ¿fijo un objetivo numérico (p. ej. ~15 mil movimientos en total) o lo ajusto hasta el límite de los 5 s de siembra?

Sin tu respuesta a (1) no empiezo D1: toca datos ya existentes y el propio contrato.
