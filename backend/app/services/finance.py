"""Finance data services (pure Python + SQL, no framework imports) so both the
FastAPI backend and the MCP server can reuse them."""
from datetime import date, timedelta

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def month_range(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = date(end_year, end_month, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


# ---------- accounts & cards ----------

def list_accounts(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def total_balance(conn) -> float:
    return round(conn.execute("SELECT COALESCE(SUM(balance),0) FROM accounts").fetchone()[0], 2)


def list_cards(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
    return [dict(r) for r in rows]


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
    if tx_type in ("income", "expense"):
        sql += " AND type = ?"; params.append(tx_type)
    if q:
        sql += " AND lower(description) LIKE ?"; params.append(f"%{q.lower()}%")
    sql += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(min(max(int(limit), 1), 500))
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


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
    if tx_type in ("income", "expense"):
        sql += " AND type = ?"; params.append(tx_type)
    if q:
        sql += " AND lower(description) LIKE ?"; params.append(f"%{q.lower()}%")
    return conn.execute(sql, params).fetchone()[0]


# ---------- analysis ----------

def spending_by_category(conn, date_from: str, date_to: str) -> list[dict]:
    rows = conn.execute(
        "SELECT category, SUM(amount) AS amount, COUNT(*) AS count FROM transactions"
        " WHERE type='expense' AND date >= ? AND date <= ?"
        " GROUP BY category ORDER BY amount DESC",
        (date_from, date_to),
    ).fetchall()
    total = sum(r["amount"] for r in rows) or 1.0
    return [
        {
            "category": r["category"],
            "amount": round(r["amount"], 2),
            "count": r["count"],
            "pct": round(100 * r["amount"] / total, 1),
        }
        for r in rows
    ]


def monthly_summary(conn, year: int, month: int) -> dict:
    date_from, date_to = month_range(year, month)
    income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income' AND date>=? AND date<=?",
        (date_from, date_to),
    ).fetchone()[0]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense' AND date>=? AND date<=?",
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
        "income": round(income, 2),
        "expense": round(expense, 2),
        "net": round(income - expense, 2),
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
                "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS n FROM transactions"
                " WHERE type='expense' AND date>=? AND date<=? AND category=?",
                (date_from, date_to, category),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS n FROM transactions"
                " WHERE type='expense' AND date>=? AND date<=?",
                (date_from, date_to),
            ).fetchone()
        out.append({
            "month": f"{y}-{m:02d}",
            "label": f"{MONTHS_ES[m - 1].capitalize()} {y}",
            "total": round(row["total"], 2),
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
            "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS n FROM transactions"
            " WHERE type='expense' AND date>=? AND date<=?",
            (w_from.isoformat(), w_to.isoformat()),
        ).fetchone()
        out.append({
            "week": w + 1,
            "label": f"Semana del {w_from.strftime('%d/%m')}",
            "from": w_from.isoformat(),
            "to": w_to.isoformat(),
            "total": round(row["total"], 2),
            "count": row["n"],
        })
    return out


def _mx(value: float) -> str:
    """Mexican format for detail strings: '$348.90', '$14,800', '-$1,234.50'."""
    v = round(abs(value), 2)
    text = f"${v:,.2f}" if v % 1 else f"${v:,.0f}"
    return f"-${text}" if value < 0 else text


def recurring_charges(conn, min_occurrences: int = 3, min_distinct_months: int = 6) -> list[dict]:
    """Merchants/charges that repeat with a similar amount in most months.

    A charge only counts as a fixed monthly payment if it appears in at least
    `min_distinct_months` different months (seasonal one-offs like a December
    gift, or repeated partial charges, are excluded).
    """
    rows = conn.execute(
        "SELECT description, COUNT(*) AS n,"
        " COUNT(DISTINCT substr(date, 1, 7)) AS months_count,"
        " AVG(amount) AS avg_amount,"
        " MIN(amount) AS min_amount, MAX(amount) AS max_amount"
        " FROM transactions WHERE type='expense'"
        " GROUP BY description HAVING n >= ?",
        (min_occurrences,),
    ).fetchall()
    out = []
    for r in rows:
        if r["months_count"] < min_distinct_months:
            continue
        spread = (r["max_amount"] - r["min_amount"]) / r["avg_amount"] if r["avg_amount"] else 1
        if spread <= 0.45:  # roughly stable amount → recurring
            cat_row = conn.execute(
                "SELECT category FROM transactions WHERE description=? LIMIT 1",
                (r["description"],),
            ).fetchone()
            out.append({
                "description": r["description"],
                "category": cat_row["category"] if cat_row else "Otros",
                "occurrences": r["n"],
                "months_count": r["months_count"],
                "avg_amount": round(r["avg_amount"], 2),
                "monthly_estimate": round(r["avg_amount"], 2),
            })
    return sorted(out, key=lambda x: -x["monthly_estimate"])


def detect_duplicates(conn) -> list[dict]:
    """Same description + amount charged more than once the same day."""
    dup_rows = conn.execute(
        "SELECT date, description, amount, COUNT(*) AS n FROM transactions"
        " WHERE type='expense' GROUP BY date, description, amount HAVING n > 1"
        " ORDER BY date DESC LIMIT 10",
    ).fetchall()
    return [{
        "kind": "duplicado",
        "date": r["date"],
        "description": r["description"],
        "amount": round(r["amount"], 2),
        "detail": f"El cargo '{r['description']}' aparece {r['n']} veces el mismo día "
                  f"por {_mx(r['amount'])} cada uno.",
    } for r in dup_rows]


def detect_anomalies(conn) -> list[dict]:
    """Charges unusually high *for their own category*, excluding fixed
    recurring payments (rent etc.) and duplicated charges."""
    recurring = {c["description"] for c in recurring_charges(conn)}
    duplicates = {(d["date"], d["description"]) for d in detect_duplicates(conn)}
    anomalies: list[dict] = []
    rows = conn.execute(
        "SELECT date, description, amount, category FROM transactions"
        " WHERE type='expense' ORDER BY amount DESC LIMIT 60",
    ).fetchall()
    cat_stats: dict[str, dict] = {}
    for r in rows:
        cat = r["category"]
        if cat not in cat_stats:
            s = conn.execute(
                "SELECT AVG(amount) AS mean FROM transactions"
                " WHERE type='expense' AND category=?",
                (cat,),
            ).fetchone()
            cat_stats[cat] = s["mean"] or 0
    for r in rows:
        if r["description"] in recurring or (r["date"], r["description"]) in duplicates:
            continue
        cat_mean = cat_stats.get(r["category"], 0)
        threshold = max(cat_mean * 4, 5_000)
        if r["amount"] >= threshold:
            anomalies.append({
                "kind": "inusual",
                "date": r["date"],
                "description": r["description"],
                "amount": round(r["amount"], 2),
                "category": r["category"],
                "detail": f"Cargo por {_mx(r['amount'])} en {r['category']}, muy por encima de "
                          f"lo típico de esa categoría ({_mx(cat_mean)}).",
            })
    return anomalies[:10]


# ---------- savings goals ----------

def list_goals(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall()
    goals = []
    for r in rows:
        g = dict(r)
        g["progress_pct"] = round(100 * g["saved_amount"] / g["target_amount"], 1) if g["target_amount"] else 0
        goals.append(g)
    return goals


def create_goal(conn, name: str, target_amount: float, deadline: str | None = None,
                saved_amount: float = 0) -> dict:
    existing = {row["name"].strip().lower()
                for row in conn.execute("SELECT name FROM savings_goals")}
    if name.strip().lower() in existing:
        raise ValueError(f"Ya tienes una meta llamada '{name}'. Elige otro nombre.")
    cur = conn.execute(
        "INSERT INTO savings_goals (name, target_amount, saved_amount, deadline) VALUES (?,?,?,?)",
        (name, target_amount, saved_amount, deadline),
    )
    row = conn.execute("SELECT * FROM savings_goals WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_goal(conn, goal_id: int, name: str | None = None, target_amount: float | None = None,
                saved_amount: float | None = None, add_amount: float | None = None,
                deadline: str | None = None, status: str | None = None) -> dict | None:
    row = conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone()
    if not row:
        return None
    goal = dict(row)
    if name is not None:
        goal["name"] = name
    if target_amount is not None:
        goal["target_amount"] = target_amount
    if saved_amount is not None:
        goal["saved_amount"] = saved_amount
    if add_amount is not None:
        goal["saved_amount"] += add_amount
    if deadline is not None:
        goal["deadline"] = deadline
    if status is not None:
        goal["status"] = status
    elif goal["saved_amount"] >= goal["target_amount"]:
        goal["status"] = "completada"
    conn.execute(
        "UPDATE savings_goals SET name=?, target_amount=?, saved_amount=?, deadline=?, status=? WHERE id=?",
        (goal["name"], goal["target_amount"], goal["saved_amount"], goal["deadline"],
         goal["status"], goal_id),
    )
    updated = dict(conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone())
    updated["progress_pct"] = round(100 * updated["saved_amount"] / updated["target_amount"], 1) \
        if updated["target_amount"] else 0
    return updated


# ---------- budgets ----------

def list_budgets(conn) -> dict[str, float]:
    rows = conn.execute("SELECT category, monthly_limit FROM budgets ORDER BY category").fetchall()
    return {r["category"]: r["monthly_limit"] for r in rows}


def set_budget_limit(conn, category: str, monthly_limit: float) -> dict:
    conn.execute(
        "INSERT INTO budgets (category, monthly_limit) VALUES (?,?)"
        " ON CONFLICT(category) DO UPDATE SET monthly_limit=excluded.monthly_limit",
        (category, monthly_limit),
    )
    return {"category": category, "monthly_limit": monthly_limit}


def budget_overview(conn, year: int, month: int) -> dict:
    date_from, date_to = month_range(year, month)
    limits = list_budgets(conn)
    spent_rows = conn.execute(
        "SELECT category, SUM(amount) AS spent FROM transactions"
        " WHERE type='expense' AND date>=? AND date<=? GROUP BY category",
        (date_from, date_to),
    ).fetchall()
    spent_by = {r["category"]: r["spent"] for r in spent_rows}
    categories = []
    for cat in sorted(set(limits) | set(spent_by)):
        spent = round(spent_by.get(cat, 0), 2)
        limit = limits.get(cat, 0)
        categories.append({
            "category": cat,
            "spent": spent,
            "limit": limit,
            "pct": round(100 * spent / limit, 1) if limit else None,
        })
    summary = monthly_summary(conn, year, month)
    total_spent = round(sum(c["spent"] for c in categories), 2)
    return {
        "month": f"{year}-{month:02d}",
        "income": summary["income"],
        "total_spent": total_spent,
        "available": round(summary["income"] - total_spent, 2),
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
