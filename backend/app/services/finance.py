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
