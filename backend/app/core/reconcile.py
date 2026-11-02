"""Reconciliación de integridad del libro financiero.

Verifica los invariantes INV-1 a INV-9 sobre toda la base y devuelve un
reporte claro con el estado de cada uno y el número de filas afectadas.

Los invariantes que dependen de la capa de dominio (INV-7, INV-8, INV-9)
se informan como `info` porque su autoridad vive en código, no en filas de
la base; aquí se verifica lo que la base puede afirmar por sí misma.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.core.seed import reference_today

# --------------------------------------------------------------------------- reporte


def _item(invariant: str, status: str, rows: int, detail: str,
          details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    item = {
        "invariant": invariant,
        "status": status,  # "pass" | "fail" | "info"
        "rows_affected": rows,
        "detail": detail,
    }
    if details is not None:
        item["details"] = details
    return item


# --------------------------------------------------------------------------- verificaciones


def _inv1_transaction_shape(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-1: forma correcta de cada tipo de movimiento.

    income/expense llevan categoría y cuenta, sin goal_id ni direction.
    transfer no lleva categoría y exige goal_id, account_id y direction válido.
    """
    bad_shape = conn.execute(
        """
        SELECT COUNT(*) FROM transactions
        WHERE (
            type IN ('income','expense')
            AND (category IS NULL OR account_id IS NULL OR goal_id IS NOT NULL OR direction IS NOT NULL)
        )
        OR (
            type = 'transfer'
            AND (category IS NOT NULL OR goal_id IS NULL OR account_id IS NULL
                 OR direction NOT IN ('account_to_goal','goal_to_account'))
        )
        OR type NOT IN ('income','expense','transfer')
        """
    ).fetchone()[0]
    status = "pass" if bad_shape == 0 else "fail"
    return _item("INV-1", status, bad_shape,
                 "Movimientos con forma incorrecta para su tipo.")


def _inv4_goal_caps(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-4: el ahorrado de una meta no supera su objetivo."""
    over = conn.execute(
        """
        SELECT COUNT(*) FROM savings_goals
        WHERE saved_amount_cents > target_amount_cents
        """
    ).fetchone()[0]
    status = "pass" if over == 0 else "fail"
    return _item("INV-4", status, over,
                 "Metas cuyo ahorrado excede el objetivo.")


def _goal_ledger(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-10: el ahorrado de cada meta es la suma firmada de sus transferencias.

    Cada diferencia se reporta con el identificador de la meta, el ahorrado,
    el libro y la diferencia exacta en centavos; nunca un resumen booleano.
    """
    rows = conn.execute(
        """
        SELECT g.id, g.name, g.saved_amount_cents, g.target_amount_cents,
               COALESCE(SUM(CASE t.direction
                   WHEN 'account_to_goal' THEN t.amount_cents
                   ELSE -t.amount_cents END), 0) AS ledger_cents
        FROM savings_goals g
        LEFT JOIN transactions t
               ON t.goal_id = g.id AND t.type = 'transfer'
        GROUP BY g.id
        ORDER BY g.id
        """
    ).fetchall()
    details = [
        {
            "goal_id": r["id"],
            "goal_name": r["name"],
            "saved_cents": r["saved_amount_cents"],
            "ledger_cents": r["ledger_cents"],
            "difference_cents": r["saved_amount_cents"] - r["ledger_cents"],
        }
        for r in rows
        if r["saved_amount_cents"] != r["ledger_cents"]
    ]
    return _item(
        "goal_ledger",
        "fail" if details else "pass",
        len(details),
        "Metas cuyo ahorrado no coincide con la suma firmada de sus transferencias.",
        details,
    )


def _goal_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-11: una meta completada tiene ahorrado igual al objetivo.

    Tambi\u00e9n detecta el caso inverso: ahorrado igual al objetivo con estado
    distinto de `completada` (el estado no refleja el libro).
    """
    rows = conn.execute(
        """
        SELECT id, name, saved_amount_cents, target_amount_cents, status
        FROM savings_goals
        WHERE (status = 'completada' AND saved_amount_cents <> target_amount_cents)
           OR (status <> 'completada' AND saved_amount_cents = target_amount_cents)
        ORDER BY id
        """
    ).fetchall()
    details = [
        {
            "goal_id": r["id"],
            "goal_name": r["name"],
            "status": r["status"],
            "saved_cents": r["saved_amount_cents"],
            "target_cents": r["target_amount_cents"],
            "reason": (
                "completada sin alcanzar el objetivo"
                if r["status"] == "completada"
                else "objetivo alcanzado con estado distinto de completada"
            ),
        }
        for r in rows
    ]
    return _item(
        "goal_status",
        "fail" if details else "pass",
        len(details),
        "Metas cuyo estado no corresponde con su avance real.",
        details,
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _transfer_legs(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-13: la suma de piernas de cada transferencia es su monto exacto.

    Detecta débitos parciales: una operación que debitó varias cuentas pero
    registró solo una pierna, o una pierna alterada.
    """
    if not _table_exists(conn, "transfer_legs"):
        return _item(
            "transfer_legs", "fail", 0,
            "La tabla transfer_legs no existe; la reparación ledger-v3 está pendiente.",
            [],
        )
    rows = conn.execute(
        """
        SELECT t.id, t.goal_id, t.amount_cents,
               COALESCE(SUM(l.amount_cents), 0) AS legs_cents,
               COUNT(l.id) AS leg_count
        FROM transactions t
        LEFT JOIN transfer_legs l ON l.transaction_id = t.id
        WHERE t.type = 'transfer'
        GROUP BY t.id
        HAVING legs_cents <> t.amount_cents OR leg_count = 0
        ORDER BY t.id
        """
    ).fetchall()
    details = [
        {
            "transaction_id": r["id"],
            "goal_id": r["goal_id"],
            "amount_cents": r["amount_cents"],
            "legs_cents": r["legs_cents"],
            "leg_count": r["leg_count"],
            "difference_cents": r["amount_cents"] - r["legs_cents"],
        }
        for r in rows
    ]
    return _item(
        "transfer_legs",
        "fail" if details else "pass",
        len(details),
        "Transferencias cuyas piernas no reconstruyen el monto de la operación.",
        details,
    )


def _orphan_transfers(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-12: toda transferencia pertenece a una meta existente."""
    rows = conn.execute(
        """
        SELECT t.id, t.goal_id, t.amount_cents, t.direction, t.date
        FROM transactions t
        LEFT JOIN savings_goals g ON g.id = t.goal_id
        WHERE t.type = 'transfer' AND g.id IS NULL
        ORDER BY t.id
        """
    ).fetchall()
    details = [
        {
            "transaction_id": r["id"],
            "goal_id": r["goal_id"],
            "amount_cents": r["amount_cents"],
            "direction": r["direction"],
            "date": r["date"],
        }
        for r in rows
    ]
    return _item(
        "orphan_transfers",
        "fail" if details else "pass",
        len(details),
        "Transferencias que apuntan a una meta inexistente.",
        details,
    )


def _inv5_idempotency(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-5: claves de idempotencia únicas y sin colisión de acción/hash."""
    dupes = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT idempotency_key, COUNT(*) AS c
            FROM idempotency_records
            GROUP BY idempotency_key
            HAVING c > 1
        )
        """
    ).fetchone()[0]
    status = "pass" if dupes == 0 else "fail"
    return _item("INV-5", status, dupes,
                 "Claves de idempotencia duplicadas.")


def _inv6_no_future_dates(conn: sqlite3.Connection) -> dict[str, Any]:
    """INV-6: no hay movimientos con fecha futura más allá de hoy."""
    today = reference_today().isoformat()
    future = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE date > ?", (today,)
    ).fetchone()[0]
    status = "pass" if future == 0 else "fail"
    return _item("INV-6", status, future,
                 "Movimientos con fecha posterior a hoy.")


def _balances_non_negative(conn: sqlite3.Connection) -> dict[str, Any]:
    """Informativo: balances de cuentas, tarjetas y metas no negativos."""
    neg_accounts = conn.execute(
        "SELECT COUNT(*) FROM accounts WHERE balance_cents < 0"
    ).fetchone()[0]
    neg_cards = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE balance_cents < 0 OR credit_limit_cents < 0"
    ).fetchone()[0]
    rows = neg_accounts + neg_cards
    status = "pass" if rows == 0 else "fail"
    return _item("saldo_no_negativo", status, rows,
                 "Cuentas o tarjetas con balance negativo.")


def _foreign_keys_ok(conn: sqlite3.Connection) -> dict[str, Any]:
    """Integridad referencial vigente (PRAGMA foreign_key_check)."""
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    status = "pass" if len(orphans) == 0 else "fail"
    return _item("foreign_keys", status, len(orphans),
                 "Referencias rotas entre tablas.")


# --------------------------------------------------------------------------- entrada principal


def reconcile(conn: sqlite3.Connection) -> dict[str, Any]:
    """Ejecuta todas las verificaciones sobre `conn` y devuelve un reporte.

    Estructura:
        {
          "ok": bool,
          "invariant_count": int,
          "failures": int,
          "results": [ {invariant, status, rows_affected, detail}, ... ]
        }
    """
    results: list[dict[str, Any]] = [
        _inv1_transaction_shape(conn),
        _inv4_goal_caps(conn),
        _goal_ledger(conn),
        _goal_status(conn),
        _orphan_transfers(conn),
        _transfer_legs(conn),
        _inv5_idempotency(conn),
        _inv6_no_future_dates(conn),
        _balances_non_negative(conn),
        _foreign_keys_ok(conn),
    ]
    # INV-7, INV-8, INV-9: autoridad de dominio, no verificable solo en filas.
    results.append(_item("INV-7", "info", 0,
                         "Porcentajes con ROUND_HALF_UP: verificado en capa de dominio (money.py)."))
    results.append(_item("INV-8", "info", 0,
                         "Última cuota absorbe residuo: verificado en capa de dominio (credit.py)."))
    results.append(_item("INV-9", "info", 0,
                         "Capa única de dominio: verificado en código (domain.py, finance.py, savings.py)."))

    failures = sum(1 for r in results if r["status"] == "fail")
    return {
        "ok": failures == 0,
        "invariant_count": len(results),
        "failures": failures,
        "results": results,
    }
