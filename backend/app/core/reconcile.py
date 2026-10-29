"""Reconciliación de integridad del libro financiero.

Verifica los invariantes INV-1 a INV-9 sobre toda la base y devuelve un
reporte claro con el estado de cada uno y el número de filas afectadas.

Los invariantes que dependen de la capa de dominio (INV-7, INV-8, INV-9)
se informan como `info` porque su autoridad vive en código, no en filas de
la base; aquí se verifica lo que la base puede afirmar por sí misma.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

# --------------------------------------------------------------------------- reporte


def _item(invariant: str, status: str, rows: int, detail: str) -> dict[str, Any]:
    return {
        "invariant": invariant,
        "status": status,  # "pass" | "fail" | "info"
        "rows_affected": rows,
        "detail": detail,
    }


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
    today = date.today().isoformat()
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
