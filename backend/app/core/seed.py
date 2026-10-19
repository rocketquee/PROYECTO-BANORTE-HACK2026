"""Synthetic demo data. Clearly fictional, deterministic (fixed seed), no real credentials."""
import random
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'MXN'
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    last4 TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    credit_limit REAL NOT NULL DEFAULT 0,
    closing_day INTEGER,
    due_day INTEGER
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('income','expense')),
    category TEXT NOT NULL,
    account_id INTEGER REFERENCES accounts(id)
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
CREATE TABLE IF NOT EXISTS savings_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    saved_amount REAL NOT NULL DEFAULT 0,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'activa',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL UNIQUE,
    monthly_limit REAL NOT NULL
);
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

# (description, category, (min, max) amount, daily probability)
SPEND_CATALOG = [
    ("Soriana", "Supermercado", (280, 1450), 0.22),
    ("Bodega Aurrerá", "Supermercado", (150, 700), 0.18),
    ("OXXO", "Tiendas de conveniencia", (35, 260), 0.45),
    ("Uber", "Transporte", (45, 230), 0.40),
    ("Gasolinera Pemex", "Transporte", (400, 850), 0.10),
    ("Rappi", "Restaurantes", (160, 620), 0.20),
    ("Tacos El Güero", "Restaurantes", (80, 240), 0.25),
    ("Starbucks", "Restaurantes", (65, 190), 0.18),
    ("Cinépolis", "Entretenimiento", (95, 260), 0.08),
    ("Farmacia Guadalajara", "Salud", (90, 480), 0.10),
    ("Liverpool", "Hogar", (450, 2400), 0.05),
    ("Mercado Libre", "Hogar", (200, 1500), 0.08),
    ("Udemy", "Educación", (199, 499), 0.03),
]

MONTHLY_EXPENSES = [
    ("Renta departamento", "Hogar", 5_500.00, 3),
    ("Internet Izzi", "Servicios", 599.00, 5),
    ("CFE", "Servicios", 480.00, 8),
    ("Netflix", "Entretenimiento", 299.00, 6),
    ("Spotify", "Entretenimiento", 169.00, 10),
    ("Gimnasio Smart Fit", "Salud", 450.00, 12),
]

MONTHLY_INCOME = [("Depósito de nómina", 22_000.00, 1)]

DEFAULT_BUDGETS = [
    ("Supermercado", 5_000),
    ("Restaurantes", 3_000),
    ("Transporte", 2_500),
    ("Entretenimiento", 1_200),
    ("Servicios", 2_000),
    ("Hogar", 8_500),
    ("Salud", 1_000),
    ("Educación", 800),
    ("Tiendas de conveniencia", 700),
]

DEFAULT_GOALS = [
    ("Fondo de emergencia", 30_000, 18_500, None),
    ("Viaje a Japón", 45_000, 8_200, None),
]


def init_db(conn) -> None:
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] > 0:
        return  # already seeded; data persists across restarts

    rng = random.Random(42)
    today = date.today()
    start = today - timedelta(days=120)

    for name, type_, balance in ACCOUNTS:
        conn.execute(
            "INSERT INTO accounts (name, type, balance) VALUES (?,?,?)",
            (name, type_, balance),
        )
    for name, type_, last4, balance, limit, closing, due in CARDS:
        conn.execute(
            "INSERT INTO cards (name, type, last4, balance, credit_limit, closing_day, due_day)"
            " VALUES (?,?,?,?,?,?,?)",
            (name, type_, last4, balance, limit, closing, due),
        )

    account_ids = [r[0] for r in conn.execute("SELECT id FROM accounts").fetchall()]
    txs = []
    d = start
    while d <= today:
        day = d.day
        for desc, amount, pay_day in MONTHLY_INCOME:
            if day == pay_day:
                txs.append((d.isoformat(), desc, amount, "income", "Ingresos", account_ids[0]))
        for desc, category, amount, pay_day in MONTHLY_EXPENSES:
            if day == pay_day and d <= today:
                txs.append((d.isoformat(), desc, amount, "expense", category, account_ids[0]))
        for desc, category, (lo, hi), prob in SPEND_CATALOG:
            if rng.random() < prob:
                amount = round(rng.uniform(lo, hi), 2)
                txs.append((d.isoformat(), desc, amount, "expense", category, rng.choice(account_ids)))
        d += timedelta(days=1)

    conn.executemany(
        "INSERT INTO transactions (date, description, amount, type, category, account_id)"
        " VALUES (?,?,?,?,?,?)",
        txs,
    )

    conn.executemany("INSERT INTO budgets (category, monthly_limit) VALUES (?,?)", DEFAULT_BUDGETS)

    deadline_emerg = (date(today.year + (1 if today.month > 3 else 0), 3, 28)).isoformat()
    conn.execute(
        "INSERT INTO savings_goals (name, target_amount, saved_amount, deadline) VALUES (?,?,?,?)",
        ("Fondo de emergencia", 30_000, 18_500, deadline_emerg),
    )
    conn.execute(
        "INSERT INTO savings_goals (name, target_amount, saved_amount, deadline) VALUES (?,?,?,?)",
        ("Viaje a Japón", 45_000, 8_200, (date(today.year + 1, 8, 1)).isoformat()),
    )


def _cat_of(desc: str) -> str:
    return {
        "Renta departamento": "Hogar",
        "Internet Izzi": "Servicios",
        "CFE": "Servicios",
        "Netflix": "Entretenimiento",
        "Spotify": "Entretenimiento",
        "Gimnasio Smart Fit": "Salud",
    }.get(desc, "Otros")
