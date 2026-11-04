"""Confirmaciones persistentes, de un solo uso y ligadas a sesión/principal."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass

from app.core.database import db
from app.schemas.ui import PendingAction
from app.services.mcp_client import MCPClientError

CONFIRMATION_TTL_SECONDS = 30 * 60
MAX_PENDING_PER_SESSION = 20


class ConfirmationError(MCPClientError):
    def __init__(self, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Claim:
    action: str
    params: dict
    trace_id: str | None
    replay: dict | None


def new_action_id() -> str:
    """Token público de confirmación; solo su hash se guarda en la base."""
    return "pa_" + secrets.token_urlsafe(24)


def _token_hash(action_id: str) -> str:
    return hashlib.sha256(action_id.encode("utf-8")).hexdigest()


def register(
    action: PendingAction,
    *,
    session_id: str,
    trace_id: str | None = None,
    principal_id: str = "local",
) -> None:
    params = dict(action.params)
    if action.action == "create_savings_goal":
        params.setdefault("idempotency_key", str(uuid.uuid4()))
    now = int(time.time())
    token_hash = _token_hash(action.id)
    with db() as conn:
        conn.execute(
            "DELETE FROM pending_confirmations WHERE expires_at <= ?", (now,),
        )
        conn.execute(
            "INSERT INTO pending_confirmations"
            " (token_hash, session_id, principal_id, trace_id, action,"
            "  params_json, created_at, expires_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                token_hash, session_id, principal_id, trace_id, action.action,
                json.dumps(params, ensure_ascii=False, sort_keys=True),
                now, now + CONFIRMATION_TTL_SECONDS,
            ),
        )
        rows = conn.execute(
            "SELECT token_hash FROM pending_confirmations"
            " WHERE session_id=? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
        for row in rows[MAX_PENDING_PER_SESSION:]:
            conn.execute(
                "DELETE FROM pending_confirmations WHERE token_hash=?",
                (row["token_hash"],),
            )


def claim(action_id: str, *, session_id: str | None,
          principal_id: str = "local") -> Claim:
    if not session_id:
        raise ConfirmationError("La confirmación requiere una sesión válida.")
    now = int(time.time())
    token_hash = _token_hash(action_id)
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM pending_confirmations WHERE token_hash=?",
            (token_hash,),
        ).fetchone()
        if row is None or row["session_id"] != session_id \
                or row["principal_id"] != principal_id:
            raise ConfirmationError(
                "La acción de confirmación no existe o ya fue procesada."
            )
        if row["expires_at"] <= now:
            raise ConfirmationError(
                "Esta confirmación ya venció. Vuelve a pedir la acción para revisar los datos.",
                status_code=410,
            )
        if row["consumed_at"] is not None:
            if row["result_json"] is not None:
                return Claim(
                    action=row["action"],
                    params=json.loads(row["params_json"]),
                    trace_id=row["trace_id"],
                    replay=json.loads(row["result_json"]),
                )
            raise ConfirmationError(
                "La confirmación ya está en proceso. Espera un momento.",
            )
        cursor = conn.execute(
            "UPDATE pending_confirmations SET consumed_at=?"
            " WHERE token_hash=? AND consumed_at IS NULL",
            (now, token_hash),
        )
        if cursor.rowcount != 1:
            raise ConfirmationError(
                "La acción de confirmación no existe o ya fue procesada."
            )
        return Claim(
            action=row["action"],
            params=json.loads(row["params_json"]),
            trace_id=row["trace_id"],
            replay=None,
        )


def finish(action_id: str, result: dict) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE pending_confirmations SET result_json=?"
            " WHERE token_hash=? AND consumed_at IS NOT NULL",
            (
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                _token_hash(action_id),
            ),
        )


def release(action_id: str) -> None:
    """Libera una confirmación cuyo tool falló antes de completar la escritura."""
    with db() as conn:
        conn.execute(
            "UPDATE pending_confirmations SET consumed_at=NULL"
            " WHERE token_hash=? AND result_json IS NULL",
            (_token_hash(action_id),),
        )
