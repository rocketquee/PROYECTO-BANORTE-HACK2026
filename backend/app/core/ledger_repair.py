"""Reparación explícita del libro (ledger-v3): piernas, fila 967 y aperturas.

No se ejecuta al arrancar. Se usa desde la línea de comandos:

    python -m app.core.ledger_repair --db <copia.db> --plan
    python -m app.core.ledger_repair --db <copia.db> --apply --accept-openings

Garantías:
- El plan es de solo lectura y se imprime antes de tocar nada.
- `--apply` crea un respaldo persistente **antes** de abrir la transacción,
  verifica su SHA-256, y aplica todo dentro de `BEGIN IMMEDIATE`.
- Las aperturas de meta nunca se inventan en silencio: solo se crean con
  `--accept-openings` y cada una se reporta con meta, monto, cuenta y folio.
- Las diferencias que no se pueden reconstruir (p. ej. ahorro menor que el
  libro) se reportan como ambiguas y **no** se modifican.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from app.core import migrate, money, seed

OPENING_DESCRIPTION = "Apertura de meta (reparación ledger-v3)"


class RepairError(RuntimeError):
    pass


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _has_table(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _signed_ledger(conn, goal_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(CASE direction WHEN 'account_to_goal'"
        " THEN amount_cents ELSE -amount_cents END), 0)"
        " FROM transactions WHERE type='transfer' AND goal_id=?",
        (goal_id,),
    ).fetchone()[0]


def _goal_balances(conn, swaps: list[dict] | None = None) -> list[dict]:
    """Saldos por meta; `swaps` proyecta correcciones aún no aplicadas."""
    projected: dict[int, int] = {}
    for item in swaps or []:
        if item.get("action") != "swap_back":
            continue
        amount = item["amount_cents"]
        projected[item["current_goal_id"]] = (
            projected.get(item["current_goal_id"], 0) - amount
        )
        projected[item["planned_goal_id"]] = (
            projected.get(item["planned_goal_id"], 0) + amount
        )
    balances = []
    for r in conn.execute(
        "SELECT id, name, saved_amount_cents, target_amount_cents, status"
        " FROM savings_goals ORDER BY id"
    ):
        ledger = _signed_ledger(conn, r["id"]) + projected.get(r["id"], 0)
        balances.append({
            "goal_id": r["id"],
            "goal_name": r["name"],
            "saved_cents": r["saved_amount_cents"],
            "ledger_cents": ledger,
            "target_cents": r["target_amount_cents"],
            "status": r["status"],
            "difference_cents": r["saved_amount_cents"] - ledger,
        })
    return balances


def _swapped(conn) -> list[dict]:
    """Filas del ledger-v1 cuyo `goal_id` no coincide con el plan registrado.

    El defecto original intercambió `account_id` y `goal_id`. La corrección se
    deriva del plan que la propia migración guardó, nunca de un id fijo.
    """
    row = conn.execute(
        "SELECT result_json FROM schema_migrations WHERE version='ledger-v1'"
    ).fetchone()
    if row is None:
        return []
    try:
        planned = json.loads(row["result_json"]).get("reclassified", [])
    except (TypeError, ValueError):
        return []
    findings = []
    for entry in planned:
        tx_id = entry.get("id")
        goal_id = entry.get("goal_id")
        tx = conn.execute(
            "SELECT id, amount_cents, account_id, goal_id FROM transactions WHERE id=?",
            (tx_id,),
        ).fetchone()
        if tx is None or tx["goal_id"] == goal_id:
            continue
        # Patrón del intercambio: la cuenta guardada es la meta planeada y el
        # goal guardado es la cuenta original.
        if tx["account_id"] == goal_id:
            findings.append({
                "transaction_id": tx_id,
                "planned_goal_id": goal_id,
                "current_goal_id": tx["goal_id"],
                "current_account_id": tx["account_id"],
                "restored_account_id": tx["goal_id"],
                "amount_cents": tx["amount_cents"],
                "action": "swap_back",
            })
        else:
            findings.append({
                "transaction_id": tx_id,
                "planned_goal_id": goal_id,
                "current_goal_id": tx["goal_id"],
                "current_account_id": tx["account_id"],
                "amount_cents": tx["amount_cents"],
                "action": "ambiguous",
            })
    return findings


def _missing_legs(conn) -> list[dict]:
    if not _has_table(conn, "transfer_legs"):
        return [
            {
                "transaction_id": r["id"],
                "account_id": r["account_id"],
                "amount_cents": r["amount_cents"],
                "action": "backfill_one_leg",
            }
            for r in conn.execute(
                "SELECT id, account_id, amount_cents FROM transactions"
                " WHERE type='transfer' ORDER BY id"
            )
        ]
    return [
        {
            "transaction_id": r["id"],
            "account_id": r["account_id"],
            "amount_cents": r["amount_cents"],
            "action": "backfill_one_leg",
        }
        for r in conn.execute(
            "SELECT t.id, t.account_id, t.amount_cents FROM transactions t"
            " LEFT JOIN transfer_legs l ON l.transaction_id=t.id"
            " WHERE t.type='transfer' GROUP BY t.id HAVING COUNT(l.id)=0"
            " ORDER BY t.id"
        )
    ]


def _opening_candidates(conn, swaps: list[dict] | None = None) -> list[dict]:
    account = conn.execute(
        "SELECT id FROM accounts ORDER BY balance_cents DESC, id LIMIT 1"
    ).fetchone()
    account_id = int(account["id"]) if account else None
    candidates = []
    for goal in _goal_balances(conn, swaps):
        diff = goal["difference_cents"]
        if diff > 0:
            candidates.append({
                "goal_id": goal["goal_id"],
                "goal_name": goal["goal_name"],
                "amount_cents": diff,
                "account_id": account_id,
                "action": "opening_transfer",
            })
        elif diff < 0:
            candidates.append({
                "goal_id": goal["goal_id"],
                "goal_name": goal["goal_name"],
                "amount_cents": -diff,
                "action": "ambiguous_saved_below_ledger",
            })
    return candidates


def plan(conn) -> dict:
    """Informe de solo lectura con todo lo que la reparación haría."""
    swaps = _swapped(conn)
    return {
        "mode": "plan",
        "schema_has_transfer_legs": _has_table(conn, "transfer_legs"),
        "swapped_rows": swaps,
        "missing_legs": _missing_legs(conn),
        # Las aperturas se calculan con la corrección de filas ya proyectada.
        "opening_candidates": _opening_candidates(conn, swaps),
        "goals": _goal_balances(conn),
        "goals_after_swaps": _goal_balances(conn, swaps),
    }


def _ensure_legs_table(conn) -> None:
    if not _has_table(conn, "transfer_legs"):
        conn.executescript(seed.TRANSFER_LEGS_DDL)


def _apply_swaps(conn, findings: list[dict]) -> list[dict]:
    applied = []
    for item in findings:
        if item["action"] != "swap_back":
            continue
        conn.execute(
            "UPDATE transactions SET account_id=?, goal_id=? WHERE id=?",
            (item["restored_account_id"], item["planned_goal_id"],
             item["transaction_id"]),
        )
        applied.append({
            "transaction_id": item["transaction_id"],
            "account_id": item["restored_account_id"],
            "goal_id": item["planned_goal_id"],
        })
    return applied


def _apply_legs(conn, findings: list[dict]) -> list[dict]:
    applied = []
    for item in findings:
        if item["account_id"] is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO transfer_legs"
            " (transaction_id, account_id, amount_cents) VALUES (?,?,?)",
            (item["transaction_id"], item["account_id"], item["amount_cents"]),
        )
        applied.append(item)
    return applied


def _apply_openings(conn, candidates: list[dict], date_str: str) -> list[dict]:
    applied = []
    for item in candidates:
        if item["action"] != "opening_transfer":
            continue
        if item["account_id"] is None:
            raise RepairError("No hay cuentas para registrar la apertura de meta.")
        goal = conn.execute(
            "SELECT id, saved_amount_cents, target_amount_cents FROM savings_goals"
            " WHERE id=?", (item["goal_id"],),
        ).fetchone()
        original_saved = goal["saved_amount_cents"]
        amount_cents = item["amount_cents"]
        if original_saved != amount_cents:
            raise RepairError(
                f"La apertura de la meta {item['goal_id']} no coincide con su diferencia."
            )
        # La apertura reconoce un ahorro que ya existía: no debe volver a
        # sumarse. Se pone el ahorro en cero para que el trigger de INV-4 mida
        # contra el estado previo y luego se restaura el valor original.
        conn.execute("UPDATE savings_goals SET saved_amount_cents=0 WHERE id=?",
                     (goal["id"],))
        cursor = conn.execute(
            "INSERT INTO transactions"
            " (date, description, amount_cents, type, category, account_id,"
            "  goal_id, direction) VALUES (?,?,?,'transfer',NULL,?,?,"
            "  'account_to_goal')",
            (date_str, OPENING_DESCRIPTION, amount_cents, item["account_id"],
             goal["id"]),
        )
        transaction_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO transfer_legs (transaction_id, account_id, amount_cents)"
            " VALUES (?,?,?)",
            (transaction_id, item["account_id"], amount_cents),
        )
        conn.execute("UPDATE savings_goals SET saved_amount_cents=? WHERE id=?",
                     (original_saved, goal["id"]))
        applied.append({
            "goal_id": goal["id"],
            "goal_name": item["goal_name"],
            "amount_cents": amount_cents,
            "account_id": item["account_id"],
            "transaction_id": transaction_id,
        })
    return applied


def _verify(conn, *, require_goals: bool = True) -> None:
    problems = []
    for goal in _goal_balances(conn):
        if require_goals and goal["difference_cents"] != 0:
            problems.append(
                f"meta {goal['goal_id']}: ahorrado {goal['saved_cents']} ≠ libro "
                f"{goal['ledger_cents']}"
            )
        if (goal["status"] == "completada") != (
            goal["saved_cents"] == goal["target_cents"]
        ):
            problems.append(f"meta {goal['goal_id']}: estado inconsistente")
    for row in conn.execute(
        "SELECT t.id, t.amount_cents, COALESCE(SUM(l.amount_cents),0) AS legs"
        " FROM transactions t LEFT JOIN transfer_legs l ON l.transaction_id=t.id"
        " WHERE t.type='transfer' GROUP BY t.id"
    ):
        if row["amount_cents"] != row["legs"]:
            problems.append(
                f"transferencia {row['id']}: piernas {row['legs']} ≠ monto "
                f"{row['amount_cents']}"
            )
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        problems.append("integridad referencial rota")
    if problems:
        raise RepairError("; ".join(problems))


def run(db_path: Path | str, *, apply: bool = False,
        accept_openings: bool = False, allow_real: bool = False) -> dict:
    db_path = Path(db_path)
    if not db_path.exists():
        raise RepairError(f"No existe la base de datos: {db_path}")
    is_real_db = db_path.resolve() == Path(migrate.DB_PATH).resolve()
    # La base real solo se toca tras aprobación explícita del informe.
    if is_real_db and apply and not allow_real:
        raise RepairError(
            "Reparación bloqueada sobre la base real; ejecútala primero sobre "
            "una copia y solicita aprobación del informe. Para la base real "
            "usa --apply --allow-real."
        )

    if not apply:
        conn = _connect(db_path)
        try:
            return plan(conn)
        finally:
            conn.close()

    backup_path = migrate.backup(db_path)
    conn = _connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            before = plan(conn)
            _ensure_legs_table(conn)
            swaps = _apply_swaps(conn, before["swapped_rows"])
            # Las piernas se calculan después de corregir la fila: la cuenta
            # restaurada es la que debe quedar ligada a la operación.
            legs = _apply_legs(conn, _missing_legs(conn))
            openings = []
            if accept_openings:
                openings = _apply_openings(
                    conn, _opening_candidates(conn),
                    datetime.now().strftime("%Y-%m-%d"),
                )
            _verify(conn, require_goals=accept_openings)
            after = plan(conn)
            result = {
                "mode": "applied",
                "applied_swaps": swaps,
                "applied_legs": legs,
                "applied_legs_count": len(legs),
                "applied_openings": openings,
                "accept_openings": accept_openings,
                "before": before,
                "after": after,
                "backup": backup_path.name,
                "backup_sha256": backup_path.with_name(
                    backup_path.name + ".sha256"
                ).read_text(encoding="utf-8").strip(),
            }
            audit_path = backup_path.with_name(
                f"{db_path.name}.repair-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            )
            audit_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            conn.execute("COMMIT")
            result["audit_file"] = str(audit_path)
            return result
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reparación explícita del libro (ledger-v3).")
    parser.add_argument("--db", required=True, help="ruta de la base SQLite (usa una copia)")
    parser.add_argument("--plan", action="store_true", help="solo informe, no escribe")
    parser.add_argument("--apply", action="store_true", help="aplica con respaldo y transacción")
    parser.add_argument("--allow-real", action="store_true",
                        help="permite --apply sobre la base real (requiere autorización)")
    parser.add_argument("--accept-openings", action="store_true",
                        help="crea movimientos de apertura para ahorro sin respaldo")
    args = parser.parse_args(argv)
    try:
        if args.apply:
            report = run(Path(args.db), apply=True,
                         accept_openings=args.accept_openings,
                         allow_real=args.allow_real)
        else:
            report = run(Path(args.db), apply=False)
    except (RepairError, migrate.MigrationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
