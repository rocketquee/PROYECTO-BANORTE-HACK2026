"""Synthetic demo data. Clearly fictional, deterministic (fixed seed), no real credentials.

12 months of coherent data: fortnightly payroll, annual bonus (aguinaldo),
fixed payments, subscriptions, everyday merchants, ant spending, one
unusually expensive month, recurring charges, one duplicated charge and one
month with extra income — so temporal analysis tools have realistic material.

Dinero en **centavos enteros** (decisión aprobada): el esquema almacena
`*_cents INTEGER`. El generador produce importes de demostración en pesos
(datos ficticios) y los convierte **solo** con `app.core.money.to_cents` en
la frontera de inserción; ninguna otra capa convierte.
"""
import os
import random
from datetime import date, timedelta

from app.core import money
from app.services import finance

# Libro de movimientos de tres tipos. La forma de cada tipo se hace cumplir
# con un CHECK: income/expense llevan categoría y cuenta; transfer no lleva
# categoría y exige meta y sentido (ver docs/DOMAIN.md §2 y §6).
TRANSACTIONS_DDL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    type TEXT NOT NULL CHECK (type IN ('income','expense','transfer')),
    category TEXT,
    account_id INTEGER REFERENCES accounts(id),
    goal_id INTEGER REFERENCES savings_goals(id),
    direction TEXT,
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
"""

TRANSACTIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
"""

# DDL canónico por tabla. `SCHEMA` es su concatenación; las migraciones
# reutilizan las entradas individuales para reconstruir tablas.
TABLE_DDL: dict[str, str] = {
    "accounts": """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    balance_cents INTEGER NOT NULL DEFAULT 0 CHECK (balance_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'MXN'
);
""",
    "cards": """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    last4 TEXT NOT NULL,
    balance_cents INTEGER NOT NULL DEFAULT 0 CHECK (balance_cents >= 0),
    credit_limit_cents INTEGER NOT NULL DEFAULT 0 CHECK (credit_limit_cents >= 0),
    closing_day INTEGER,
    due_day INTEGER
);
""",
    "savings_goals": """
CREATE TABLE IF NOT EXISTS savings_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount_cents INTEGER NOT NULL CHECK (target_amount_cents > 0),
    saved_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (saved_amount_cents >= 0),
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'activa',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
""",
    "transactions": TRANSACTIONS_DDL,
    "idempotency_records": """
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
""",
    "budgets": """
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL UNIQUE,
    monthly_limit_cents INTEGER NOT NULL CHECK (monthly_limit_cents > 0)
);
""",
}

SCHEMA = "".join(TABLE_DDL[name] for name in
                 ("accounts", "cards", "savings_goals", "transactions")) \
    + TRANSACTIONS_INDEXES + TABLE_DDL["idempotency_records"] + TABLE_DDL["budgets"]

# Restricciones que no se pueden expresar como CHECK de tabla (INV-3 e INV-4).
# Se aplican en el motor, en centavos enteros, para que ninguna capa pueda
# violarlas.
TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_goal_saved_bounds_ins
BEFORE INSERT ON savings_goals
WHEN NEW.saved_amount_cents < 0 OR NEW.saved_amount_cents > NEW.target_amount_cents
BEGIN SELECT RAISE(ABORT, 'INV-4: el ahorrado debe estar entre 0 y el objetivo de la meta'); END;

CREATE TRIGGER IF NOT EXISTS trg_goal_saved_bounds_upd
BEFORE UPDATE OF saved_amount_cents, target_amount_cents ON savings_goals
WHEN NEW.saved_amount_cents < 0 OR NEW.saved_amount_cents > NEW.target_amount_cents
BEGIN SELECT RAISE(ABORT, 'INV-4: el ahorrado debe estar entre 0 y el objetivo de la meta'); END;

CREATE TRIGGER IF NOT EXISTS trg_transfer_within_goal_bounds
BEFORE INSERT ON transactions
WHEN NEW.type = 'transfer'
BEGIN
  SELECT RAISE(ABORT, 'INV-4: la aportación supera lo que falta para la meta')
  WHERE NEW.direction = 'account_to_goal'
    AND (SELECT saved_amount_cents FROM savings_goals WHERE id = NEW.goal_id) + NEW.amount_cents
        > (SELECT target_amount_cents FROM savings_goals WHERE id = NEW.goal_id);
  SELECT RAISE(ABORT, 'INV-4: el retiro supera lo ahorrado en la meta')
  WHERE NEW.direction = 'goal_to_account'
    AND (SELECT saved_amount_cents FROM savings_goals WHERE id = NEW.goal_id) - NEW.amount_cents < 0;
END;

CREATE TRIGGER IF NOT EXISTS trg_account_balance_non_negative
BEFORE UPDATE OF balance_cents ON accounts
WHEN NEW.balance_cents < 0
BEGIN SELECT RAISE(ABORT, 'INV-3: el saldo disponible no puede ser negativo'); END;
"""


ACCOUNTS = [
    ("Cuenta Nómina", "debit", 24_580.35),
    ("Cuenta Ahorro", "savings", 58_200.00),
    ("Cuenta Digital", "debit", 3_140.80),
]

CARDS = [
    ("Tarjeta de Crédito Principal", "credit", "4412", 8_450.50, 30_000, 28, 5),
    ("Tarjeta de Débito Nómina", "debit", "9903", 0, 0, None, None),
]

# Everyday merchants: (description, category, (min, max) amount, monthly frequency)
SPEND_CATALOG = [
    ("Soriana", "Supermercado", (320, 1_450), 7.0),
    ("Bodega Aurrerá", "Supermercado", (180, 720), 4.0),
    ("Chedraui", "Supermercado", (450, 1_800), 2.0),
    ("OXXO", "Tiendas de conveniencia", (35, 120), 12.0),
    ("Café La Parroquia", "Tiendas de conveniencia", (38, 95), 10.0),
    ("Uber", "Transporte", (45, 230), 10.0),
    ("Gasolinera Pemex", "Transporte", (400, 850), 4.0),
    ("Rappi", "Restaurantes", (160, 620), 5.0),
    ("Tacos El Güero", "Restaurantes", (80, 240), 6.0),
    ("Starbucks", "Restaurantes", (65, 190), 4.0),
    ("Cinépolis", "Entretenimiento", (95, 320), 2.0),
    ("Farmacia Guadalajara", "Salud", (90, 480), 2.0),
    ("Mercado Libre", "Hogar", (200, 1_500), 2.0),
    ("Udemy", "Educación", (199, 499), 0.6),
]

# Fixed monthly payments: (description, category, base amount, jitter, day of month)
MONTHLY_EXPENSES = [
    ("Renta departamento", "Hogar", 5_500.00, 0.0, 3),
    ("Internet Izzi", "Servicios", 599.00, 0.0, 5),
    ("CFE", "Servicios", 480.00, 0.35, 8),
    ("Agua SAPAE", "Servicios", 245.00, 0.30, 10),
    ("Telcel", "Servicios", 349.00, 0.0, 12),
    ("Netflix", "Entretenimiento", 299.00, 0.0, 6),
    ("Spotify", "Entretenimiento", 169.00, 0.0, 10),
    ("iCloud", "Servicios", 29.00, 0.0, 7),
    ("Gimnasio Smart Fit", "Salud", 450.00, 0.0, 12),
    ("Seguro de vida GNP", "Seguros", 480.00, 0.0, 15),
    ("Pago tarjeta de crédito", "Tarjetas", 1_600.00, 0.45, 25),
]

DEFAULT_BUDGETS = [
    ("Supermercado", 6_500),
    ("Restaurantes", 3_000),
    ("Transporte", 2_500),
    ("Entretenimiento", 1_500),
    ("Servicios", 2_500),
    ("Hogar", 9_000),
    ("Salud", 1_500),
    ("Educación", 800),
    ("Tiendas de conveniencia", 900),
    ("Seguros", 500),
    ("Tarjetas", 2_500),
    ("Regalos", 1_500),
]

DEFAULT_GOALS = [
    ("Fondo de emergencia", 30_000, 18_500, None),
    ("Viaje a Japón", 45_000, 8_200, None),
    # El nombre no puede coincidir con el que reserva el flujo de plan de compra
    # (`orchestrator`: "Compra planeada"); si coincidiera, crear esa meta desde
    # el flujo fallaría por nombre duplicado.
    ("Enganche del auto", 45_000, 0, None),
]

# Fondeo declarado de la meta "Enganche del auto": entra al libro como
# transferencia cuenta→meta (INV-1), no como gasto, y ajusta el disponible por
# su monto exacto (INV-3). Mantiene la demo reproducible en cualquier máquina.
SEED_TRANSFERS = [
    ("Enganche del auto", 22_500.00),
]


def _month_add(y: int, m: int, delta: int) -> tuple[int, int]:
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return y, m


def _reference_today() -> date:
    """Fecha de referencia de la demo.

    Por defecto es hoy (los análisis relativos al mes en curso necesitan datos
    recientes). Para una semilla **idéntica en cualquier máquina**, define
    `BANORTE_DEMO_TODAY` (AAAA-MM-DD): el generador ya es determinista
    (`random.Random(42)`), solo falta fijar el calendario.
    """
    raw = os.getenv("BANORTE_DEMO_TODAY", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return date.today()


def init_db(conn, reference_date: date | None = None) -> None:
    conn.executescript(SCHEMA)
    conn.executescript(TRIGGERS)
    if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] > 0:
        return  # already seeded; data persists across restarts

    rng = random.Random(42)
    today = reference_date or _reference_today()
    start_y, start_m = _month_add(today.year, today.month, -11)
    start = date(start_y, start_m, 1)

    for name, type_, balance in ACCOUNTS:
        conn.execute(
            "INSERT INTO accounts (name, type, balance_cents) VALUES (?,?,?)",
            (name, type_, money.to_cents(balance)),
        )
    for name, type_, last4, balance, limit, closing, due in CARDS:
        conn.execute(
            "INSERT INTO cards (name, type, last4, balance_cents, credit_limit_cents,"
            " closing_day, due_day) VALUES (?,?,?,?,?,?,?)",
            (name, type_, last4, money.to_cents(balance), money.to_cents(limit),
             closing, due),
        )

    account_ids = [r[0] for r in conn.execute("SELECT id FROM accounts").fetchall()]
    nomina_id = account_ids[0]
    txs: list[tuple[str, str, float, str, str, int]] = []

    # Electric appliance: the "unusual charge", lands 4 months ago.
    unusual_y, unusual_m = _month_add(today.year, today.month, -4)
    unusual_day = min(17, (date(unusual_y, unusual_m, 28)).day)

    # Duplicated charge: a Rappi order registered twice on the same day, last month.
    dup_y, dup_m = _month_add(today.year, today.month, -1)
    dup_day = 14

    high_spend_key = f"{unusual_y}-{unusual_m:02d}"  # month with an unusually high expense

    d = start
    while d <= today:
        y, m, day = d.year, d.month, d.day
        key = f"{y}-{m:02d}"

        # --- income: fortnightly payroll with slight variation ---
        last_day = (date(y, m % 12 + 1, 1) - timedelta(days=1)).day if m < 12 else 31
        if day in (15, last_day):
            amount = round(11_000 + rng.uniform(-60, 60), 2)
            txs.append((d.isoformat(), "Depósito de nómina", amount, "income", "Ingresos", nomina_id))
        if m == 12 and day == 15:  # aguinaldo
            txs.append((d.isoformat(), "Aguinaldo", 22_000.00, "income", "Ingresos", nomina_id))
        if key == f"{_month_add(today.year, today.month, -3)[0]}-{_month_add(today.year, today.month, -3)[1]:02d}" and day == 20:
            txs.append((d.isoformat(), "Bono de desempeño", 6_500.00, "income", "Ingresos", nomina_id))

        # --- fixed payments & subscriptions ---
        for desc, category, base, jitter, pay_day in MONTHLY_EXPENSES:
            if day == pay_day:
                amount = round(base * (1 + rng.uniform(-jitter, jitter)), 2)
                txs.append((d.isoformat(), desc, amount, "expense", category, nomina_id))

        # --- the unusual charge (one-off appliance) ---
        if key == high_spend_key and day == unusual_day:
            txs.append((d.isoformat(), "Electrodoméstico Liverpool", 14_800.00, "expense", "Hogar", nomina_id))

        # --- the duplicated charge ---
        if key == f"{dup_y}-{dup_m:02d}" and day == dup_day:
            txs.append((d.isoformat(), "Rappi pedido #8817", 348.90, "expense", "Restaurantes", account_ids[2]))
            txs.append((d.isoformat(), "Rappi pedido #8817", 348.90, "expense", "Restaurantes", account_ids[2]))

        # --- December gifts (high-spend season) ---
        if m == 12 and day in (5, 12, 19):
            txs.append((d.isoformat(), "Regalo Navidad", round(rng.uniform(350, 1_400), 2),
                        "expense", "Regalos", nomina_id))

        # --- everyday spending ---
        for desc, category, (lo, hi), freq in SPEND_CATALOG:
            expected = freq / 30.0
            if rng.random() < expected:
                amount = round(rng.uniform(lo, hi), 2)
                txs.append((d.isoformat(), desc, amount, "expense", category,
                            rng.choice(account_ids)))
        d += timedelta(days=1)

    txs.sort(key=lambda t: t[0])
    # Frontera única pesos→centavos: los importes generados (datos de demo)
    # entran al libro como centavos enteros.
    conn.executemany(
        "INSERT INTO transactions (date, description, amount_cents, type, category, account_id)"
        " VALUES (?,?,?,?,?,?)",
        [(d, desc, money.to_cents(amount), type_, cat, acc)
         for d, desc, amount, type_, cat, acc in txs],
    )

    conn.executemany(
        "INSERT INTO budgets (category, monthly_limit_cents) VALUES (?,?)",
        [(cat, money.to_cents(limit)) for cat, limit in DEFAULT_BUDGETS],
    )

    deadline_emerg = (date(today.year + (1 if today.month > 3 else 0), 3, 28)).isoformat()
    for name, target, saved, _ in DEFAULT_GOALS:
        dl = deadline_emerg if name == "Fondo de emergencia" else (date(today.year + 1, 8, 1)).isoformat()
        conn.execute(
            "INSERT INTO savings_goals (name, target_amount_cents, saved_amount_cents, deadline)"
            " VALUES (?,?,?,?)",
            (name, money.to_cents(target), money.to_cents(saved), dl),
        )

    # El fondeo declarado se aplica por el libro, no escribiendo el ahorrado a
    # mano: así la fila existe con type='transfer' y las cotas se cumplen.
    for goal_name, amount in SEED_TRANSFERS:
        goal_row = conn.execute(
            "SELECT id FROM savings_goals WHERE name=?", (goal_name,)
        ).fetchone()
        finance.apply_transfer(conn, goal_id=goal_row["id"], amount=amount,
                               direction="account_to_goal", date_str=today.isoformat())
