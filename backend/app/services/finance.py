"""Finance data services (pure Python + SQL, no framework imports) so both the
FastAPI backend and the MCP server can reuse them.

Dinero: la base almacena **centavos enteros** (`*_cents`) y todo el cálculo
interno ocurre en centavos (sin flotantes). La conversión pesos↔centavos
ocurre **solo** en `app.core.money` (frontera de API); las firmas públicas
siguen hablando en pesos para que el contrato no cambie.
"""
from datetime import date, timedelta

from app.core import money

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Tipos del libro de movimientos (INV-1) y sentidos válidos de una
# transferencia cuenta↔meta. Definición única: `domain.py` la reutiliza.
LEDGER_TYPES = ("income", "expense", "transfer")
TRANSFER_DIRECTIONS = ("account_to_goal", "goal_to_account")


def month_range(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = date(end_year, end_month, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


# ---------- accounts & cards ----------

def list_accounts(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["balance"] = money.to_pesos(item.pop("balance_cents"))
        out.append(item)
    return out


def accounts_balance_cents(conn) -> int:
    """Saldo en cuentas, en centavos: lo único que se puede mover a metas (INV-3)."""
    return conn.execute("SELECT COALESCE(SUM(balance_cents),0) FROM accounts").fetchone()[0]


def goals_balance_cents(conn) -> int:
    """Ahorro acumulado en metas, en centavos (parte del patrimonio, INV-2)."""
    return conn.execute(
        "SELECT COALESCE(SUM(saved_amount_cents),0) FROM savings_goals"
    ).fetchone()[0]


def accounts_balance(conn) -> float:
    return money.to_pesos(accounts_balance_cents(conn))


def goals_balance(conn) -> float:
    return money.to_pesos(goals_balance_cents(conn))


def total_balance_cents(conn) -> int:
    """Patrimonio en centavos = saldo en cuentas + ahorro en metas (INV-2).

    Una transferencia entre cuentas propias y metas **no** lo modifica.
    """
    return accounts_balance_cents(conn) + goals_balance_cents(conn)


def total_balance(conn) -> float:
    return money.to_pesos(total_balance_cents(conn))


def available_balance(conn) -> float:
    """Disponible = saldo en cuentas (INV-3).

    Es distinto de `total_balance`: el dinero ahorrado en metas no está
    disponible para gastar ni para aportar a otra meta.
    """
    return accounts_balance(conn)


def list_cards(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["balance"] = money.to_pesos(item.pop("balance_cents"))
        item["credit_limit"] = money.to_pesos(item.pop("credit_limit_cents"))
        out.append(item)
    return out


# ---------- transactions ----------

def list_transactions(conn, date_from: str | None = None, date_to: str | None = None,
                      category: str | None = None, tx_type: str | None = None,
                      q: str | None = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list = []
    if date_from:
        sql += " AND date >= ?"; params.append(date_from)
    if date_to:
        sql += " AND date <= ?"; params.append(date_to)
    if category:
        sql += " AND category = ?"; params.append(category)
    if tx_type in LEDGER_TYPES:
        sql += " AND type = ?"; params.append(tx_type)
    if q:
        sql += " AND lower(description) LIKE ?"; params.append(f"%{q.lower()}%")
    sql += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(min(max(int(limit), 1), 500))
    out = []
    for r in conn.execute(sql, params).fetchall():
        item = dict(r)
        item["amount"] = money.to_pesos(item.pop("amount_cents"))
        out.append(item)
    return out


def count_transactions(conn, date_from: str | None = None, date_to: str | None = None,
                       category: str | None = None, tx_type: str | None = None,
                       q: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM transactions WHERE 1=1"
    params: list = []
    if date_from:
        sql += " AND date >= ?"; params.append(date_from)
    if date_to:
        sql += " AND date <= ?"; params.append(date_to)
    if category:
        sql += " AND category = ?"; params.append(category)
    if tx_type in LEDGER_TYPES:
        sql += " AND type = ?"; params.append(tx_type)
    if q:
        sql += " AND lower(description) LIKE ?"; params.append(f"%{q.lower()}%")
    return conn.execute(sql, params).fetchone()[0]


def category_taxonomy(conn, limit: int = 500) -> list[str]:
    """Categorías de gasto presentes en el libro.

    El tipo `transfer` no tiene categoría (INV-1), así que se excluye del
    conjunto: comparar `None` con texto en un `sorted` falla. Es la única
    definición de la taxonomía para todos los consumidores (REST, MCP, agente).
    """
    return sorted({
        t["category"] for t in list_transactions(conn, limit=limit)
        if t["category"] is not None
    })


# ---------- analysis ----------

def spending_by_category(conn, date_from: str, date_to: str) -> list[dict]:
    """Gasto por categoría en un periodo. El porcentaje (INV-7) declara su base:
    el gasto total del periodo, la misma base que usan los textos y gráficas."""
    rows = conn.execute(
        "SELECT category, SUM(amount_cents) AS amount_cents, COUNT(*) AS count"
        " FROM transactions"
        " WHERE type='expense' AND date >= ? AND date <= ?"
        " GROUP BY category ORDER BY amount_cents DESC",
        (date_from, date_to),
    ).fetchall()
    total_cents = sum(r["amount_cents"] for r in rows)
    return [
        {
            "category": r["category"],
            "amount": money.to_pesos(r["amount_cents"]),
            "count": r["count"],
            "pct": money.pct(r["amount_cents"], total_cents),
            "pct_base": "gasto total del periodo",
            "pct_base_value": money.to_pesos(total_cents),
        }
        for r in rows
    ]


def monthly_summary(conn, year: int, month: int) -> dict:
    date_from, date_to = month_range(year, month)
    income_cents = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) FROM transactions"
        " WHERE type='income' AND date>=? AND date<=?",
        (date_from, date_to),
    ).fetchone()[0]
    expense_cents = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) FROM transactions"
        " WHERE type='expense' AND date>=? AND date<=?",
        (date_from, date_to),
    ).fetchone()[0]
    count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE date>=? AND date<=?", (date_from, date_to)
    ).fetchone()[0]
    categories = spending_by_category(conn, date_from, date_to)
    return {
        "year": year,
        "month": month,
        "month_label": f"{MONTHS_ES[month - 1].capitalize()} {year}",
        "income": money.to_pesos(income_cents),
        "expense": money.to_pesos(expense_cents),
        "net": money.to_pesos(income_cents - expense_cents),
        "transaction_count": count,
        "top_categories": categories[:5],
    }


def monthly_series(conn, months: int = 6) -> list[dict]:
    today = date.today()
    out = []
    y, m = today.year, today.month
    keys = []
    for _ in range(months):
        keys.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    for y, m in reversed(keys):
        s = monthly_summary(conn, y, m)
        out.append({"month": f"{y}-{m:02d}", "label": MONTHS_ES[m - 1][:3].capitalize(),
                    "income": s["income"], "expense": s["expense"]})
    return out


def _prev_month(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def spending_trend(conn, months: int = 4, category: str | None = None) -> list[dict]:
    """Total expense per month for the last `months` months (oldest first)."""
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(max(1, min(months, 24))):
        keys.append((y, m))
        y, m = _prev_month(y, m)
    out = []
    for y, m in reversed(keys):
        date_from, date_to = month_range(y, m)
        if category:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_cents),0) AS total_cents, COUNT(*) AS n"
                " FROM transactions"
                " WHERE type='expense' AND date>=? AND date<=? AND category=?",
                (date_from, date_to, category),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_cents),0) AS total_cents, COUNT(*) AS n"
                " FROM transactions"
                " WHERE type='expense' AND date>=? AND date<=?",
                (date_from, date_to),
            ).fetchone()
        out.append({
            "month": f"{y}-{m:02d}",
            "label": f"{MONTHS_ES[m - 1].capitalize()} {y}",
            "total": money.to_pesos(row["total_cents"]),
            "count": row["n"],
        })
    return out


def weekly_spending(conn, weeks: int = 4) -> list[dict]:
    """Total expense per ISO week for the last `weeks` weeks (oldest first)."""
    today = date.today()
    out = []
    start = today - timedelta(days=7 * weeks + today.weekday())
    for w in range(weeks):
        w_from = start + timedelta(days=7 * w)
        w_to = w_from + timedelta(days=6)
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS total_cents, COUNT(*) AS n"
            " FROM transactions WHERE type='expense' AND date>=? AND date<=?",
            (w_from.isoformat(), w_to.isoformat()),
        ).fetchone()
        out.append({
            "week": w + 1,
            "label": f"Semana del {w_from.strftime('%d/%m')}",
            "from": w_from.isoformat(),
            "to": w_to.isoformat(),
            "total": money.to_pesos(row["total_cents"]),
            "count": row["n"],
        })
    return out


def _mx(value: float) -> str:
    """Mexican format for detail strings: '$348.90', '$14,800', '-$1,234.50'."""
    v = money.boundary(abs(value))
    text = f"${v:,.2f}" if v % 1 else f"${v:,.0f}"
    return f"-{text}" if value < 0 else text


def recurring_charges(conn, min_occurrences: int = 3, min_distinct_months: int = 6) -> list[dict]:
    """Merchants/charges that repeat with a similar amount in most months.

    A charge only counts as a fixed monthly payment if it appears in at least
    `min_distinct_months` different months (seasonal one-offs like a December
    gift, or repeated partial charges, are excluded).
    """
    rows = conn.execute(
        "SELECT description, COUNT(*) AS n,"
        " COUNT(DISTINCT substr(date, 1, 7)) AS months_count,"
        " SUM(amount_cents) AS sum_cents,"
        " MIN(amount_cents) AS min_cents, MAX(amount_cents) AS max_cents"
        " FROM transactions WHERE type='expense'"
        " GROUP BY description HAVING n >= ?",
        (min_occurrences,),
    ).fetchall()
    out = []
    for r in rows:
        if r["months_count"] < min_distinct_months:
            continue
        avg_cents = r["sum_cents"] / r["n"]  # promedio en centavos (fraccionario)
        spread_cents = (r["max_cents"] - r["min_cents"]) / avg_cents if avg_cents else 1
        if spread_cents <= 0.45:  # roughly stable amount → recurring
            cat_row = conn.execute(
                "SELECT category FROM transactions WHERE description=? LIMIT 1",
                (r["description"],),
            ).fetchone()
            estimate = money.to_pesos(money.round_half_up(avg_cents))
            out.append({
                "description": r["description"],
                "category": cat_row["category"] if cat_row else "Otros",
                "occurrences": r["n"],
                "months_count": r["months_count"],
                "avg_amount": estimate,
                "monthly_estimate": estimate,
            })
    return sorted(out, key=lambda x: -x["monthly_estimate"])


def detect_duplicates(conn) -> list[dict]:
    """Same description + amount charged more than once the same day."""
    dup_rows = conn.execute(
        "SELECT date, description, amount_cents, COUNT(*) AS n FROM transactions"
        " WHERE type='expense' GROUP BY date, description, amount_cents HAVING n > 1"
        " ORDER BY date DESC LIMIT 10",
    ).fetchall()
    return [{
        "kind": "duplicado",
        "date": r["date"],
        "description": r["description"],
        "amount": money.to_pesos(r["amount_cents"]),
        "detail": f"El cargo '{r['description']}' aparece {r['n']} veces el mismo día "
                  f"por {_mx(money.to_pesos(r['amount_cents']))} cada uno.",
    } for r in dup_rows]


def detect_anomalies(conn) -> list[dict]:
    """Charges unusually high *for their own category*, excluding fixed
    recurring payments (rent etc.) and duplicated charges."""
    recurring = {c["description"] for c in recurring_charges(conn)}
    duplicates = {(d["date"], d["description"]) for d in detect_duplicates(conn)}
    anomalies: list[dict] = []
    rows = conn.execute(
        "SELECT date, description, amount_cents, category FROM transactions"
        " WHERE type='expense' ORDER BY amount_cents DESC LIMIT 60",
    ).fetchall()
    cat_stats: dict[str, float] = {}
    for r in rows:
        cat = r["category"]
        if cat not in cat_stats:
            s = conn.execute(
                "SELECT AVG(amount_cents) AS mean_cents FROM transactions"
                " WHERE type='expense' AND category=?",
                (cat,),
            ).fetchone()
            cat_stats[cat] = s["mean_cents"] or 0
    floor_cents = money.to_cents(5_000)
    for r in rows:
        if r["description"] in recurring or (r["date"], r["description"]) in duplicates:
            continue
        cat_mean_cents = cat_stats.get(r["category"], 0)
        threshold_cents = max(cat_mean_cents * 4, floor_cents)
        if r["amount_cents"] >= threshold_cents:
            amount = money.to_pesos(r["amount_cents"])
            cat_mean = money.to_pesos(money.round_half_up(cat_mean_cents))
            anomalies.append({
                "kind": "inusual",
                "date": r["date"],
                "description": r["description"],
                "amount": amount,
                "category": r["category"],
                "detail": f"Cargo por {_mx(amount)} en {r['category']}, muy por encima de "
                          f"lo típico de esa categoría ({_mx(cat_mean)}).",
            })
    return anomalies[:10]


# ---------- savings goals ----------

def _with_progress(goal: dict) -> dict:
    """Añade el avance de una meta declarando la base del porcentaje (INV-7).

    Expone el contrato en pesos: las claves `*_cents` son internas y no
    salen de la capa de dominio.
    """
    target_cents = goal["target_amount_cents"]
    saved_cents = goal["saved_amount_cents"]
    goal.pop("target_amount_cents")
    goal.pop("saved_amount_cents")
    goal["progress_pct"] = money.pct(saved_cents, target_cents)
    goal["pct_base"] = "objetivo de la meta"
    goal["pct_base_value"] = money.to_pesos(target_cents)
    goal["target_amount"] = money.to_pesos(target_cents)
    goal["saved_amount"] = money.to_pesos(saved_cents)
    return goal


def list_goals(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall()
    return [_with_progress(dict(r)) for r in rows]


def goal_name_taken(conn, name: str, *, exclude_id: int | None = None) -> bool:
    """¿Existe ya una meta con ese nombre (sin distinguir mayúsculas ni espacios)?"""
    target = " ".join(str(name or "").split()).casefold()
    for row in conn.execute("SELECT id, name FROM savings_goals"):
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        if " ".join(row["name"].split()).casefold() == target:
            return True
    return False


def create_goal(conn, name: str, target_amount: float, deadline: str | None = None) -> dict:
    """Crea una meta con el ahorrado en cero.

    El ahorrado **nunca** se fija al crear: solo cambia por transferencias
    confirmadas (INV-4, `apply_transfer`). Un fondeo inicial es una
    transferencia cuenta→meta, no un campo de la meta.
    """
    if goal_name_taken(conn, name):
        raise ValueError(f"Ya tienes una meta llamada '{name}'. Elige otro nombre.")
    cur = conn.execute(
        "INSERT INTO savings_goals (name, target_amount_cents, saved_amount_cents, deadline)"
        " VALUES (?,?,0,?)",
        (name, money.to_cents(target_amount), deadline),
    )
    row = conn.execute("SELECT * FROM savings_goals WHERE id=?", (cur.lastrowid,)).fetchone()
    return _with_progress(dict(row))


def update_goal(conn, goal_id: int, name: str | None = None, target_amount: float | None = None,
                deadline: str | None = None, status: str | None = None) -> dict | None:
    """Actualiza los datos de una meta.

    El ahorrado **no** se modifica aquí: solo cambia por transferencias
    (INV-4, `apply_transfer`). El objetivo tampoco puede quedar por debajo de
    lo ya ahorrado.
    """
    row = conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone()
    if not row:
        return None
    goal = dict(row)
    if name is not None and name != goal["name"]:
        if goal_name_taken(conn, name, exclude_id=goal_id):
            raise ValueError(f"Ya tienes una meta llamada '{name}'. Elige otro nombre.")
        goal["name"] = name
    if target_amount is not None:
        target_cents = money.to_cents(target_amount)
        if target_cents < goal["saved_amount_cents"]:
            raise ValueError(
                f"El objetivo no puede ser menor que lo ya ahorrado "
                f"(${money.to_pesos(goal['saved_amount_cents']):,.2f})."
            )
        goal["target_amount_cents"] = target_cents
    if deadline is not None:
        goal["deadline"] = deadline
    if status is not None:
        goal["status"] = status
    elif goal["saved_amount_cents"] >= goal["target_amount_cents"]:
        goal["status"] = "completada"
    conn.execute(
        "UPDATE savings_goals SET name=?, target_amount_cents=?, deadline=?, status=? WHERE id=?",
        (goal["name"], goal["target_amount_cents"], goal["deadline"], goal["status"], goal_id),
    )
    updated = dict(conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone())
    return _with_progress(updated)


def _debit_accounts_cents(conn, amount_cents: int) -> int:
    """Debita `amount_cents` del disponible, repartiendo entre cuentas con saldo.

    Devuelve el id de la cuenta principal afectada (la de mayor saldo usada).
    """
    remaining = amount_cents
    primary: int | None = None
    rows = conn.execute(
        "SELECT id, balance_cents FROM accounts WHERE balance_cents > 0"
        " ORDER BY balance_cents DESC, id"
    ).fetchall()
    for row in rows:
        if remaining <= 0:
            break
        debit = min(remaining, row["balance_cents"])
        if debit <= 0:
            continue
        conn.execute("UPDATE accounts SET balance_cents = balance_cents - ? WHERE id=?",
                     (debit, row["id"]))
        if primary is None:
            primary = row["id"]
        remaining -= debit
    if remaining > 0:
        raise ValueError("No hay saldo suficiente en las cuentas de demostración.")
    return int(primary or 0)


def transfer_balance(conn, goal_id: int, direction: str, amount_cents: int) -> int:
    """Ahorrado resultante de aplicar la transferencia, en centavos (INV-4)."""
    row = conn.execute(
        "SELECT saved_amount_cents FROM savings_goals WHERE id=?", (goal_id,)
    ).fetchone()
    saved = row["saved_amount_cents"] if row else 0
    return saved + amount_cents if direction == "account_to_goal" else saved - amount_cents


def apply_transfer(conn, *, goal_id: int, amount: float, direction: str,
                   account_id: int | None = None, date_str: str | None = None,
                   description: str | None = None) -> dict:
    """Registra una transferencia cuenta↔meta como una única escritura.

    Un solo punto de escritura para mover dinero entre el disponible y una
    meta: ajusta el saldo de la cuenta y el ahorrado de la meta por el monto
    exacto (INV-3), conserva el saldo total (INV-2) y **no** toca ingresos,
    gastos, categorías, balance del mes, anomalías ni pagos fijos (INV-1).

    El llamador debe haber validado antes con `domain.validate_transfer`
    (INV-4) y estar dentro de una transacción abierta (INV-5).
    """
    if direction not in TRANSFER_DIRECTIONS:
        raise ValueError("La transferencia debe indicar si es una aportación o un retiro.")
    row = conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone()
    if row is None:
        raise ValueError("No encontré esa meta de ahorro.")
    amount_cents = money.to_cents(amount)
    if amount_cents <= 0:
        raise ValueError("El monto de la transferencia debe ser mayor que cero.")
    target_cents = row["target_amount_cents"]
    saved_cents = row["saved_amount_cents"]

    if direction == "account_to_goal":
        if saved_cents + amount_cents > target_cents:
            raise ValueError("El abono no puede superar lo que falta para la meta.")
        account = _debit_accounts_cents(conn, amount_cents)
        conn.execute(
            "UPDATE savings_goals SET saved_amount_cents = saved_amount_cents + ? WHERE id=?",
            (amount_cents, goal_id))
        label = f"Abono a meta: {row['name']}"
    else:
        if amount_cents > saved_cents:
            raise ValueError("El retiro no puede superar lo ahorrado en la meta.")
        if account_id is None:
            first = conn.execute("SELECT id FROM accounts ORDER BY id LIMIT 1").fetchone()
            if first is None:
                raise ValueError("No hay cuentas registradas.")
            account = int(first["id"])
        else:
            account = int(account_id)
        conn.execute("UPDATE accounts SET balance_cents = balance_cents + ? WHERE id=?",
                     (amount_cents, account))
        conn.execute(
            "UPDATE savings_goals SET saved_amount_cents = saved_amount_cents - ? WHERE id=?",
            (amount_cents, goal_id))
        label = f"Retiro de meta: {row['name']}"

    new_saved_cents = transfer_balance(conn, goal_id, direction, amount_cents)
    if new_saved_cents >= target_cents:
        conn.execute("UPDATE savings_goals SET status='completada' WHERE id=?", (goal_id,))

    conn.execute(
        "INSERT INTO transactions"
        " (date, description, amount_cents, type, category, account_id, goal_id, direction)"
        " VALUES (?,?,?,'transfer',NULL,?,?,?)",
        (date_str or date.today().isoformat(), description or label, amount_cents,
         account, goal_id, direction),
    )
    goal = dict(conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone())
    return {
        "goal": _with_progress(goal),
        "amount": money.to_pesos(amount_cents),
        "direction": direction,
        "account_id": account,
        "available_balance": available_balance(conn),
        "total_balance": total_balance(conn),
    }


# ---------- budgets ----------

def list_budgets(conn) -> dict[str, float]:
    rows = conn.execute(
        "SELECT category, monthly_limit_cents FROM budgets ORDER BY category"
    ).fetchall()
    return {r["category"]: money.to_pesos(r["monthly_limit_cents"]) for r in rows}


def set_budget_limit(conn, category: str, monthly_limit: float) -> dict:
    limit_cents = money.to_cents(monthly_limit)
    conn.execute(
        "INSERT INTO budgets (category, monthly_limit_cents) VALUES (?,?)"
        " ON CONFLICT(category) DO UPDATE SET monthly_limit_cents=excluded.monthly_limit_cents",
        (category, limit_cents),
    )
    return {"category": category, "monthly_limit": money.to_pesos(limit_cents)}


def budget_overview(conn, year: int, month: int) -> dict:
    date_from, date_to = month_range(year, month)
    limits = list_budgets(conn)
    spent_rows = conn.execute(
        "SELECT category, SUM(amount_cents) AS spent_cents FROM transactions"
        " WHERE type='expense' AND date>=? AND date<=? GROUP BY category",
        (date_from, date_to),
    ).fetchall()
    spent_by = {r["category"]: r["spent_cents"] for r in spent_rows}
    categories = []
    total_spent_cents = 0
    for cat in sorted(set(limits) | set(spent_by)):
        spent_cents = spent_by.get(cat, 0)
        total_spent_cents += spent_cents
        limit_cents = money.to_cents(limits.get(cat, 0))
        categories.append({
            "category": cat,
            "spent": money.to_pesos(spent_cents),
            "limit": money.to_pesos(limit_cents),
            "pct": money.pct(spent_cents, limit_cents) if limit_cents else None,
            "pct_base": "límite mensual de la categoría",
            "pct_base_value": money.to_pesos(limit_cents) if limit_cents else None,
        })
    summary = monthly_summary(conn, year, month)
    total_spent = money.to_pesos(total_spent_cents)
    return {
        "month": f"{year}-{month:02d}",
        "income": summary["income"],
        "total_spent": total_spent,
        "available": money.to_pesos(
            money.to_cents(summary["income"]) - total_spent_cents),
        "categories": categories,
    }


# ---------- dashboard ----------

def dashboard(conn, year: int | None = None, month: int | None = None) -> dict:
    today = date.today()
    y, m = year or today.year, month or today.month
    summary = monthly_summary(conn, y, m)
    date_from, date_to = month_range(y, m)
    return {
        "total_balance": total_balance(conn),
        "accounts": list_accounts(conn),
        "cards": list_cards(conn),
        "summary": summary,
        "categories": spending_by_category(conn, date_from, date_to),
        "monthly_series": monthly_series(conn, 6),
        "goals": list_goals(conn),
        "recent_transactions": list_transactions(conn, limit=8),
        "budget_overview": budget_overview(conn, y, m),
    }
