"""Caso de uso único de transferencias cuenta↔meta (INV-4, INV-5, INV-9).

Un solo camino para mover dinero entre el disponible y una meta: lo invocan
tanto la API REST como el servidor MCP, que son dos transportes del **mismo**
caso de uso (DOMAIN.md §7). Aquí viven la resolución de la meta, la validación
central (`domain.validate_transfer`) y la escritura idempotente
(`finance.apply_transfer`); ninguna capa vuelve a fijar `saved_amount` a mano.

El llamador debe ejecutar dentro de una transacción abierta (`BEGIN IMMEDIATE`);
este módulo no abre conexiones ni confirma (es capa de dominio pura).
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from difflib import SequenceMatcher

from app.core import money
from app.services import domain, finance

# Nombre de la acción en `idempotency_records` (INV-5): estable entre versiones.
ACTION = "apply_savings_contribution"

# Umbral de similitud para resolver una meta por nombre aproximado.
_NAME_MATCH_MIN = 0.55
_NAME_MATCH_TIE = 0.08


def validate_idempotency_key(value) -> str:
    """Valida que la clave de idempotencia sea un UUID (INV-5)."""
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("La clave de idempotencia no es válida.") from exc
    return str(value)


def validate_amount(amount) -> float:
    """Valida el monto de la transferencia antes de tocar la base."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or \
            not math.isfinite(amount) or amount <= 0:
        raise ValueError("El monto del abono debe ser mayor que cero.")
    return money.boundary(amount)


def resolve_goal(conn, goal_id, goal_name):
    """Resuelve la meta por identificador o por nombre aproximado.

    Devuelve `(row, None)` si hay una meta clara, `(None, candidates)` si el
    nombre es ambiguo, o `(None, None)` si no se encontró ninguna.
    """
    if goal_id is not None:
        if isinstance(goal_id, bool) or not isinstance(goal_id, int) or goal_id <= 0:
            raise ValueError("La meta seleccionada no es válida.")
        return conn.execute("SELECT * FROM savings_goals WHERE id=?", (goal_id,)).fetchone(), None

    query = " ".join(str(goal_name or "").casefold().split())
    ranked = sorted(
        (
            (
                1.0 if query == " ".join(row["name"].casefold().split())
                else SequenceMatcher(
                    None, query, " ".join(row["name"].casefold().split())
                ).ratio(),
                row,
            )
            for row in conn.execute("SELECT * FROM savings_goals")
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    matches = [item for item in ranked if item[0] >= _NAME_MATCH_MIN]
    if len(matches) > 1 and matches[0][0] - matches[1][0] < _NAME_MATCH_TIE:
        return None, [{"id": item[1]["id"], "name": item[1]["name"]} for item in matches[:5]]
    return (matches[0][1] if matches else None), None


def _request_hash(goal_id, amount: float, direction: str) -> str:
    payload = json.dumps(
        {"goal_id": goal_id, "amount": amount, "direction": direction},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_contribution(conn, *, amount, idempotency_key, goal_id=None, goal_name=None,
                       direction: str = "account_to_goal",
                       description: str | None = None,
                       date_str: str | None = None) -> dict:
    """Aplica una transferencia cuenta↔meta de forma atómica e idempotente.

    Requiere una transacción abierta por el llamador (INV-5). Devuelve el
    resultado aplicado; si la misma clave ya se usó con los mismos datos,
    devuelve el resultado guardado con `idempotent_replay: true`.
    """
    amount = validate_amount(amount)
    idempotency_key = validate_idempotency_key(idempotency_key)
    request_hash = _request_hash(goal_id, amount, direction)

    existing = conn.execute(
        "SELECT action, request_hash, result_json FROM idempotency_records"
        " WHERE idempotency_key=?",
        (idempotency_key,),
    ).fetchone()
    if existing:
        if existing["action"] != ACTION or existing["request_hash"] != request_hash:
            raise ValueError("La clave de idempotencia ya se usó con otros datos.")
        result = json.loads(existing["result_json"])
        result["idempotent_replay"] = True
        return result

    row, candidates = resolve_goal(conn, goal_id, goal_name)
    if candidates is not None:
        return {"status": "ambiguous", "candidates": candidates}
    if row is None:
        raise ValueError("No encontré esa meta de ahorro.")

    # Una sola autoridad de las reglas: cotas de la meta (INV-4) y disponible (INV-3).
    domain.validate_transfer(conn, goal_id=row["id"], amount=amount, direction=direction)
    transfer = finance.apply_transfer(
        conn, goal_id=row["id"], amount=amount, direction=direction,
        description=description, date_str=date_str,
    )
    movement = "Abono" if direction == "account_to_goal" else "Retiro"
    preposition = "a" if direction == "account_to_goal" else "de"
    result = {
        "status": "applied",
        "goal": transfer["goal"],
        "amount": transfer["amount"],
        "direction": transfer["direction"],
        "available_balance": transfer["available_balance"],
        "total_balance": transfer["total_balance"],
        "message": (
            f"{movement} de ${transfer['amount']:,.2f} {preposition} la meta "
            f"'{transfer['goal']['name']}'."
        ),
    }
    conn.execute(
        "INSERT INTO idempotency_records "
        "(idempotency_key, action, request_hash, result_json) VALUES (?,?,?,?)",
        (idempotency_key, ACTION, request_hash, json.dumps(result, ensure_ascii=False)),
    )
    return result
