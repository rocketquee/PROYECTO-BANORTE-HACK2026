# DATA-DICTIONARY — Diseño de esquema ampliado (Fase D1)

**Estado:** Borrador de diseño (solo diseño, sin código de migración, sin tocar la base de datos).
**Alcance:** Prioritario (perfil, cuentas, tarjetas con fecha de corte y estados de cuenta, presupuestos, metas, notificaciones, 24 meses, 3 perfiles demo).
**Fuera de alcance (D6 opcional):** inversiones, seguros, préstamos, tipo de cambio.

---

## 1. Auditoría del esquema actual

### Tablas existentes y columnas

| Tabla | Columna | Tipo | Constraints | Notas |
|-------|---------|------|-------------|-------|
| `accounts` | id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| | name | TEXT | NOT NULL | |
| | type | TEXT | NOT NULL | |
| | balance_cents | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | Dinero en centavos |
| | currency | TEXT | NOT NULL DEFAULT 'MXN' | |
| `cards` | id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| | name | TEXT | NOT NULL | |
| | type | TEXT | NOT NULL | |
| | last4 | TEXT | NOT NULL | Solo últimos 4 dígitos |
| | balance_cents | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | |
| | credit_limit_cents | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | |
| | closing_day | INTEGER | (nullable) | Día de corte (sin restricción de rango) |
| | due_day | INTEGER | (nullable) | Día límite de pago (sin restricción de rango) |
| `savings_goals` | id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| | name | TEXT | NOT NULL | |
| | target_amount_cents | INTEGER | NOT NULL, CHECK > 0 | |
| | saved_amount_cents | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | |
| | deadline | TEXT | (nullable) | Fecha ISO |
| | status | TEXT | NOT NULL DEFAULT 'activa' | |
| | created_at | TEXT | NOT NULL DEFAULT datetime('now') | |
| `transactions` | id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| | date | TEXT | NOT NULL | Fecha ISO |
| | description | TEXT | NOT NULL | |
| | amount_cents | INTEGER | NOT NULL, CHECK > 0 | |
| | type | TEXT | NOT NULL, CHECK IN ('income','expense','transfer') | |
| | category | TEXT | (nullable) | Obligatorio para income/expense vía CHECK |
| | account_id | INTEGER | REFERENCES accounts(id) | Obligatorio para income/expense |
| | goal_id | INTEGER | REFERENCES savings_goals(id) | Obligatorio para transfer |
| | direction | TEXT | (nullable) | 'account_to_goal' / 'goal_to_account' para transfer |
| `idempotency_records` | idempotency_key | TEXT | PRIMARY KEY | |
| | action | TEXT | NOT NULL | |
| | request_hash | TEXT | NOT NULL | |
| | result_json | TEXT | NOT NULL | |
| | created_at | TEXT | NOT NULL DEFAULT datetime('now') | |
| `budgets` | id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| | category | TEXT | NOT NULL, UNIQUE | Una fila por categoría |
| | monthly_limit_cents | INTEGER | NOT NULL, CHECK > 0 | Sin historial mensual |

### Índices existentes

| Índice | Tabla | Columnas |
|--------|-------|----------|
| `idx_tx_date` | transactions | date |
| `idx_tx_category` | transactions | category |

### Triggers existentes (invariantas en la base)

| Trigger | Tabla | Evento | Invariant |
|---------|-------|--------|-----------|
| `trg_goal_saved_bounds_ins` | savings_goals | BEFORE INSERT | INV-4: 0 <= saved <= target |
| `trg_goal_saved_bounds_upd` | savings_goals | BEFORE UPDATE (saved, target) | INV-4 |
| `trg_transfer_within_goal_bounds` | transactions | BEFORE INSERT (type='transfer') | INV-4: aporte <= faltante, retiro <= ahorrado |
| `trg_account_balance_non_negative` | accounts | BEFORE UPDATE balance_cents | INV-3: saldo >= 0 |

### Representación del dinero

**Ya está en centavos INTEGER.** La migración `ledger-v2` (ver `migrate.py:6-8`) convirtió de `REAL` a centavos enteros en las cinco tablas con importes. El único módulo de conversión es `app/core/money.py` (`to_cents`, `to_pesos`, `boundary`, `apply_rate`, `split_evenly`). No hay `float` en rutas de dinero.

### Invariantas INV-1 a INV-9 ya verificadas

| Invariant | Estado actual | Dónde se impone |
|-----------|---------------|-----------------|
| INV-1 | Libro de movimientos con tipos y formas correctas | `transactions` CHECK + `seed.py:23-43` |
| INV-2 | Patrimonio = cuentas + metas (transfer no lo modifica) | Capa de dominio (`finance.total_balance_cents`) |
| INV-3 | Disponible = saldo en cuentas; transfer no lo excede | `domain.validate_transfer` + trigger `trg_account_balance_non_negative` |
| INV-4 | Ahorrado <= objetivo en metas; aportación/retiro dentro de cotas | Triggers `trg_goal_saved_bounds_*` + `trg_transfer_within_goal_bounds` + `domain.validate_transfer` |
| INV-5 | Escritura idempotente con clave única | `idempotency_records.idempotency_key` PRIMARY KEY + `domain.py` |
| INV-6 | No fechas futuras | `domain.validate_period` (capa de dominio, no en base) |
| INV-7 | Porcentajes ROUND_HALF_UP con base declarada | `money.pct` (capa de dominio) |
| INV-8 | Última cuota absorbe residuo | `credit.py` (capa de dominio) |
| INV-9 | Capa única de dominio para reglas | `domain.py` + `finance.py` + `savings.py` |


## 2. Diseño del esquema ampliado (alcance prioritario)

### Principios de diseño (respetar decisiones aprobadas)

- **Dinero:** `INTEGER` en centavos en todas las columnas de importe. Única conversión vía `app/core/money.py`. Prohibido `float` en rutas de dinero.
- **Perfiles:** una sola tabla `profiles` con `profile_id`. Todas las tablas de datos transaccionales incluyen `profile_id` para que ninguna consulta suelta cruce perfiles.
- **Saldos:** derivados del libro (`transactions`). `accounts.balance_cents` es una caché derivada, regenerable; nunca fuente de verdad.
- **Cada cuenta tiene un movimiento de apertura explícito:** una transacción tipo `income` con categoría 'Apertura' al crear la cuenta.
- **Volumen:** perfil principal 3.000–5.000 movimientos; los otros dos perfiles 1.000–2.000 cada uno. 24 meses de historia.
- **3 perfiles de demostración:** seleccionables solo en modo demo; perfil por defecto = el actual.
- **Fixtures de calidad de datos:** tabla `data_quality_fixtures` marca filas intencionalmente problemáticas (duplicados, cargos atípicos, meses sin datos, nombres similares).

### Diagrama entidad-relación (Mermaid)

```mermaid
erDiagram
    profiles ||--o{ accounts : "tiene"
    profiles ||--o{ cards : "tiene"
    profiles ||--o{ savings_goals : "tiene"
    profiles ||--o{ budgets : "tiene"
    profiles ||--o{ budget_history : "tiene"
    profiles ||--o{ notifications : "recibe"
    profiles ||--o{ audit_log : "genera"
    profiles ||--o{ recurring_charges : "tiene"
    profiles ||--o{ scheduled_payments : "tiene"

    accounts ||--o{ transactions : "registra"
    accounts ||--o{ account_balance_history : "tiene saldo"
    cards ||--o{ card_statements : "emite"
    cards ||--o{ transactions : "genera pagos"
### Tablas nuevas y ampliadas (definición de columnas y reglas de negocio)

#### `profiles`
Perfil de persona y preferencias. Una fila por persona demo.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | PK | Identificador único del perfil (UUID-like) |
| `display_name` | TEXT | NOT NULL | Nombre ficticio de la persona demo |
| `email_domain_reserved` | TEXT | NOT NULL | Correo con dominio reservado para pruebas (@demo.banorte.local) |
| `language` | TEXT | NOT NULL DEFAULT 'es-MX' | Idioma de interfaz |
| `accessibility_profile` | TEXT | NOT NULL DEFAULT 'standard' | 'standard' | 'large_text' | 'high_contrast' |
| `contact_channels` | TEXT | NOT NULL DEFAULT 'none' | Canales de contacto habilitados |
| `digital_experience_level` | TEXT | NOT NULL DEFAULT 'intermedio' | 'básico' | 'intermedio' | 'avanzado' |
| `is_demo_profile` | BOOLEAN | NOT NULL DEFAULT false | Solo perfiles demo pueden tener este flag |
| `created_at` | TEXT | NOT NULL | Fecha de creación |

**Regla:** Cambiar de perfil activo solo en modo demo. El perfil activo viaja como contexto explícito al servidor MCP y se valida en el servidor.

#### `accounts` (ampliada)
Se agrega `profile_id` y `opening_transaction_id`.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | FK compuesta implícita vía acceso a datos |
| `opening_transaction_id` | INTEGER | FK -> transactions.id | Movimiento de apertura explícito (type='income', categoría='Apertura') |

**Regla:** Cada cuenta debe tener exactamente un movimiento de apertura. El saldo de la cuenta se deriva de `transactions` (suma de amount_cents por type/cuenta), no de `balance_cents` como fuente de verdad.

#### `cards` (ampliada)
Se agrega `profile_id`, `minimum_payment_pct`. `closing_day` y `due_day` se vuelven NOT NULL con rango válido.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `minimum_payment_pct` | INTEGER | NOT NULL DEFAULT 5, CHECK BETWEEN 1 AND 100 | Porcentaje para calcular pago mínimo |
| `closing_day` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 28 | Día de corte |
| `due_day` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 28 | Día límite de pago |

    savings_goals ||--o{ transactions : "recibe aportes"
    savings_goals ||--o{ goal_contribution_history : "historial"
    budgets ||--o{ budget_history : "historial mensual"
    recurring_charges ||--o{ transactions : "genera"
#### `card_statements` (nueva)
Estados de cuenta emitidos con folio, periodo y resumen.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `card_id` | INTEGER | FK -> cards.id | |
| `folio` | TEXT | NOT NULL, UNIQUE | Folio único del estado de cuenta |
| `period_start` / `period_end` | DATE | NOT NULL | Periodo de corte del estado |
| `statement_date` | DATE | NOT NULL | Fecha de emisión |
| `due_date` | DATE | NOT NULL | Fecha límite de pago |
| `previous_balance_cents` | INTEGER | NOT NULL | Saldo anterior |
| `charges_cents` | INTEGER | NOT NULL | Cargos del periodo |
| `payments_cents` | INTEGER | NOT NULL | Pagos del periodo |
| `interest_cents` | INTEGER | NOT NULL | Intereses generados |
| `current_balance_cents` | INTEGER | NOT NULL | Saldo actual |
| `minimum_payment_cents` | INTEGER | NOT NULL | Pago mínimo calculado |
| `status` | TEXT | NOT NULL DEFAULT 'emitido' | 'emitido' | 'pagado' | 'vencido' |

#### `transactions` (ampliada)
Se agrega `profile_id`, `recurring_charge_id`, `scheduled_payment_id`, `source`.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | Todas las filas incluyen profile_id |
| `recurring_charge_id` | INTEGER | FK -> recurring_charges.id | Cargo recurrente que generó esta transacción |
| `scheduled_payment_id` | INTEGER | FK -> scheduled_payments.id | Pago programado que generó esta transacción |
| `source` | TEXT | NOT NULL DEFAULT 'manual' | Origen de la transacción |

**Regla:** El acceso a datos inyecta `profile_id` en cada consulta; ninguna consulta suelta filtra solo por `account_id` o `goal_id` sin `profile_id`.

#### `savings_goals` (ampliada)
Se agrega `profile_id`.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |

**Regla:** El ahorrado (`saved_amount_cents`) solo cambia por transferencias confirmadas (`goal_contribution_history`). Nunca se escribe a mano.

#### `goal_contribution_history` (nueva)
Historial de aportaciones a metas, siempre por transferencias.

#### `budgets` (ampliada)
Se agrega `profile_id`, `month`, `spent_cents`. Se convierte en tabla con historial mensual.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `category` | TEXT | NOT NULL | |
| `month` | TEXT | NOT NULL, CHECK FORMAT 'YYYY-MM' | |
| `monthly_limit_cents` | INTEGER | NOT NULL, CHECK > 0 | |
| `spent_cents` | INTEGER | NOT NULL DEFAULT 0, CHECK >= 0 | Derivado de transactions |
| UNIQUE(profile_id, category, month) | | | Una fila por perfil/categoría/mes |

#### `budget_history` (nueva)
Captura mensual del estado del presupuesto.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `category` | TEXT | NOT NULL | |
| `month` | TEXT | NOT NULL | |
| `limit_cents` | INTEGER | NOT NULL | |
| `spent_cents` | INTEGER | NOT NULL | |
| `pct_used` | REAL | NOT NULL | Porcentaje de uso del presupuesto |

#### `notifications` (nueva)
Notificaciones y alertas del sistema.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `type` | TEXT | NOT NULL | Tipo de notificación |
| `title` | TEXT | NOT NULL | Título |
| `body` | TEXT | NOT NULL | Cuerpo del mensaje |
| `channel` | TEXT | NOT NULL | Canal de entrega |
| `scheduled_for` | DATE | (nullable) | Fecha programada |
| `status` | TEXT | NOT NULL DEFAULT 'pendiente' | 'pendiente' | 'enviada' | 'leída' |

#### `audit_log` (nueva)
Bitácora de auditoría para operaciones de escritura.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
#### `recurring_charges` (nueva)
Pagos recurrentes y suscripciones.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `name` | TEXT | NOT NULL | Nombre del cargo recurrente |
| `category` | TEXT | NOT NULL | Categoría del gasto |
| `amount_cents` | INTEGER | NOT NULL, CHECK > 0 | Monto recurrente |
| `day_of_month` | INTEGER | NOT NULL, CHECK BETWEEN 1 AND 28 | Día de cobro |
| `is_active` | BOOLEAN | NOT NULL DEFAULT true | Si el cargo está activo |

#### `scheduled_payments` (nueva)
Pagos programados futuros.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `profile_id` | TEXT | FK -> profiles.profile_id | |
| `name` | TEXT | NOT NULL | Nombre del pago programado |
| `amount_cents` | INTEGER | NOT NULL, CHECK > 0 | Monto programado |
| `scheduled_date` | DATE | NOT NULL | Fecha de ejecución |
| `status` | TEXT | NOT NULL DEFAULT 'pendiente' | 'pendiente' | 'ejecutado' | 'cancelado' |

#### `data_quality_fixtures` (nueva)
Marca filas intencionalmente problemáticas para que las pruebas las distingan sin codificar valores.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `table_name` | TEXT | NOT NULL, PK parte 1 | Tabla donde está la fila |
| `row_id` | TEXT | NOT NULL, PK parte 2 | Identificador de la fila marcada |
| `fixture_type` | TEXT | NOT NULL CHECK IN ('duplicate','anomaly','no_data_month','similar_name','edge_case') | Tipo de caso de calidad |
| `description` | TEXT | NOT NULL | Descripción del caso |
| `created_at` | TEXT | NOT NULL | Fecha de marcado |

| fixture_type | Descripción |
|--------------|-------------|
| `duplicate` | Cobro duplicado (mismo concepto, mismo monto, mismo día) |
| `anomaly` | Cargo atípico para su categoría |
| `no_data_month` | Mes sin movimientos para una entidad |
| `similar_name` | Entidades con nombres muy similares (ej. "Soriana" vs "Soriana Expreso") |
| `edge_case` | Casos de borde (montos límite, fechas límite, etc.) |


## 3. Decisiones respetadas en este diseño

| Decisión | Cómo se refleja en el diseño |
|----------|------------------------------|
| Dinero en centavos INTEGER | Todas las columnas de importe son `*_cents INTEGER`; `money.py` es la única conversión |
| Único módulo money.py | Ninguna otra tabla o capa convierte pesos↔centavos |
| Un solo profile_id | Tabla `profiles` con `profile_id`; todas las tablas transaccionales lo incluyen |
| FKs compuestas con profile_id | El acceso a datos inyecta `profile_id` en cada consulta; ninguna consulta cruza perfiles |
| Saldos derivados del libro | `accounts.balance_cents` es caché derivada; `account_balance_history` es regenerable |
| Movimiento de apertura por cuenta | `accounts.opening_transaction_id` referencia a `transactions` |
| 3 perfiles demo | `profiles.is_demo_profile`; seleccionables solo en modo demo |
| 24 meses de historia | El generador de semilla produce 24 meses |
| Volumen 3.000-5.000 / 1.000-2.000 | Especificación para el generador de D2 |
| Sin inversiones/seguros/préstamos/tipo de cambio | Quedan para D6 opcional |

## 4. Tabla de estado de la fase D1

| Elemento | Estado | Cómo verificarlo |
|----------|--------|------------------|
| Auditoría del esquema actual | Hecho (diseño) | Revisar §1 de este documento |
| Diagrama entidad-relación Mermaid | Hecho (diseño) | Revisar §2 de este documento |
| Borrador docs/DATA-DICTIONARY.md | Hecho (este archivo) | Leer este archivo |
| Tablas nuevas definidas | Hecho (diseño) | Revisar §2 de este documento |
| Migraciones versionadas escritas | No iniciado (prohibido en D1) | — |
| Base de datos tocada | No (prohibido en D1) | Comparar hash de `backend/data/banorte.db` antes/después |
| Código de D2 iniciado | No (prohibido en D1) | — |

## 5. Cómo verificarlo usted (sin tocar la base)

1. **Verificar que la base no cambió:**
   ```powershell
   Get-FileHash 'backend\data\banorte.db' -Algorithm SHA256
   ```
   Debe ser `A42AB5E198419A3494C3B940DF9B2E0485D1DCE90E6F5130D33DF2F18F174382` (mismo que antes de D1).

2. **Verificar que no hay código de migración nuevo:**
   ```powershell
   Get-ChildItem backend\app\core\migrate.py
   ```
   El archivo debe tener solo las migraciones `ledger-v1` y `ledger-v2` existentes (no `ledger-v3`).

3. **Revisar el diseño:**
   Abrir `docs/DATA-DICTIONARY.md` y confirmar que contiene el diagrama Mermaid, las tablas nuevas con `profile_id`, y las reglas de negocio.

4. **Verificar que las pruebas existentes siguen verdes (opcional, no modifica la base real):**
   ```powershell
   $env:BANORTE_DB_PATH="$env:TEMP\banorte_d1_check.db"
   .venv\Scripts\python -m pytest -c backend/pytest.ini backend/tests
   ```
   Debe mostrar `283 passed` (o el conteo actual sin las pruebas nuevas de Tramo B).

---

**Quedo a la espera de su aprobación explícita de este diseño antes de iniciar la Fase D2.**

| `actor_type` | TEXT | NOT NULL CHECK IN ('system','user','agent') | Quién ejecuta |
| `operation` | TEXT | NOT NULL | 'CREATE' | 'UPDATE' | 'DELETE' | 'TRANSFER' |
| `table_name` | TEXT | NOT NULL | Tabla afectada |
| `row_id` | TEXT | (nullable) | Identificador de la fila |
| `trace_id` | TEXT | NOT NULL | Trace ID para correlación |
| `result` | TEXT | NOT NULL CHECK IN ('ok','error','rejected') | Resultado de la operación |
| `details_json` | TEXT | (nullable) | Detalles sin datos sensibles |

**Regla:** Nunca registrar datos sensibles (nombres completos, correos reales, números de tarjeta completos) en `details_json`.

| Columna | Tipo | Constraint | Regla de negocio |
|---------|------|------------|------------------|
| `goal_id` | INTEGER | FK -> savings_goals.id | |
| `amount_cents` | INTEGER | NOT NULL, CHECK > 0 | |
| `direction` | TEXT | NOT NULL CHECK IN ('account_to_goal','goal_to_account') | |
| `transaction_id` | INTEGER | FK -> transactions.id, UNIQUE | Referencia al movimiento del libro |
| `idempotency_key` | TEXT | NOT NULL | Para detectar duplicados |

    scheduled_payments ||--o{ transactions : "genera"
```

### Brechas del esquema actual frente al alcance D1

1. **Sin `profile_id`:** ninguna tabla tiene columna de perfil. No hay aislamiento por perfil.
2. **Sin FKs compuestas:** no se puede garantizar que una consulta no cruce perfiles.
3. **Sin historial de saldos:** `accounts.balance_cents` es el único saldo; no hay serie temporal derivada.
4. **Sin estados de cuenta con folio:** `cards` tiene `closing_day`/`due_day` pero no hay tabla de estados emitidos.
5. **Sin historial mensual de presupuestos:** `budgets` es una sola fila por categoría, sin serie temporal.
6. **Sin tabla de bitácora de auditoría:** no hay registro de quién, qué, cuándo, trace_id, resultado.
7. **Sin tabla de perfiles ni preferencias:** no existe entidad de persona/preferencias.
8. **Sin fixtures de calidad de datos marcados:** no hay forma de distinguir duplicados intencionales de datos válidos.
