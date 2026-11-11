"""Memoria persistente del agente en SQLite (misma base, tabla `agent_memory`).

Esta memoria **no entrena ni ajusta el modelo**: guarda correcciones recientes y
turnos para (a) inyectar las correcciones de la misma sesión en el prompt del
siguiente turno y (b) dejar trazabilidad de lo que respondió el agente.

Aislamiento: toda lectura de correcciones filtra por `session_id`; una
corrección de otra sesión nunca se inyecta. La similitud entre mensajes usa
`LIKE` sobre `user_msg` en esta fase (deuda: embeddings/vector DB).
"""
from __future__ import annotations

import json
import sqlite3

from app.core.seed import reference_today
from app.core.structured_logging import mask_pii

KINDS = ("correction", "fact", "turn")
MAX_USER_MSG_CHARS = 1_000
MAX_ACTION_CHARS = 2_000


def _clip(value: object, limit: int) -> str:
    text = "" if value is None else str(value)
    text = mask_pii(text.replace("\x00", "").strip())
    return text[:limit]


def _created_at() -> str:
    """Fecha de referencia de la demo, no el reloj real (AGENTS.md §3)."""
    return reference_today().isoformat()


def _row_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def record_correction(conn, user_msg: str, wrong_action: str, right_action: str,
                      session_id: str) -> int:
    """Registra una corrección explícita del usuario para una sesión."""
    if not _clip(session_id, 128):
        raise ValueError("La corrección requiere session_id.")
    if not _clip(user_msg, MAX_USER_MSG_CHARS):
        raise ValueError("La corrección requiere el mensaje del usuario.")
    cursor = conn.execute(
        "INSERT INTO agent_memory"
        " (kind, user_msg, wrong_action, right_action, created_at, session_id)"
        " VALUES (?,?,?,?,?,?)",
        (
            "correction",
            _clip(user_msg, MAX_USER_MSG_CHARS),
            _clip(wrong_action, MAX_ACTION_CHARS) or None,
            _clip(right_action, MAX_ACTION_CHARS) or None,
            _created_at(),
            _clip(session_id, 128),
        ),
    )
    return int(cursor.lastrowid)


def record_fact(conn, user_msg: str, fact: str, session_id: str) -> int:
    """Registra un dato declarado por el usuario (kind='fact')."""
    if not _clip(session_id, 128):
        raise ValueError("El hecho requiere session_id.")
    if not _clip(fact, MAX_ACTION_CHARS):
        raise ValueError("El hecho requiere contenido.")
    cursor = conn.execute(
        "INSERT INTO agent_memory"
        " (kind, user_msg, wrong_action, right_action, created_at, session_id)"
        " VALUES (?,?,?,?,?,?)",
        (
            "fact",
            _clip(user_msg, MAX_USER_MSG_CHARS),
            None,
            _clip(fact, MAX_ACTION_CHARS),
            _created_at(),
            _clip(session_id, 128),
        ),
    )
    return int(cursor.lastrowid)


def record_turn(conn, session_id: str, user_msg: str, reply: str,
                tool_calls_json: str | list | dict | None) -> int:
    """Guarda un turno para trazabilidad; nunca se usa para entrenar."""
    if isinstance(tool_calls_json, str):
        serialized = tool_calls_json
    else:
        serialized = json.dumps(tool_calls_json or [], ensure_ascii=False)
    serialized = mask_pii(serialized)
    cursor = conn.execute(
        "INSERT INTO agent_memory"
        " (kind, user_msg, wrong_action, right_action, created_at, session_id,"
        "  tool_calls_json)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            "turn",
            _clip(user_msg, MAX_USER_MSG_CHARS),
            None,
            _clip(reply, MAX_ACTION_CHARS),
            _created_at(),
            _clip(session_id, 128),
            serialized,
        ),
    )
    return int(cursor.lastrowid)


def recent_corrections(conn, session_id: str, limit: int = 5) -> list[dict]:
    """Correcciones más recientes de **esa** sesión, de la más nueva a la más vieja."""
    if not _clip(session_id, 128) or limit <= 0:
        return []
    try:
        rows = conn.execute(
            "SELECT id, kind, user_msg, wrong_action, right_action, created_at,"
            " session_id, tool_calls_json"
            " FROM agent_memory"
            " WHERE kind = 'correction' AND session_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (_clip(session_id, 128), int(limit)),
        ).fetchall()
    except sqlite3.OperationalError:
        # Base anterior a `agent-memory-v1`: la memoria es opcional, no rompe el chat.
        return []
    return [_row_dict(row) for row in rows]


def counts(conn) -> dict:
    """Conteo para `/api/health`; tolera bases sin la migración aplicada."""
    result = {"corrections": 0, "turns": 0}
    try:
        rows = conn.execute(
            "SELECT kind, COUNT(*) AS total FROM agent_memory"
            " WHERE kind IN ('correction', 'turn') GROUP BY kind"
        ).fetchall()
    except sqlite3.OperationalError:
        return result
    for row in rows:
        if row["kind"] == "correction":
            result["corrections"] = int(row["total"])
        elif row["kind"] == "turn":
            result["turns"] = int(row["total"])
    return result
