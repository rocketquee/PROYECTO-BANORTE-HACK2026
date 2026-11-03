"""Almacén de estado conversacional por sesión.

Un único mapa en memoria, keyed por `session_id`, con caducidad por
inactividad y límite de sesiones activas. El estado nunca se comparte entre
sesiones distintas.
"""
from __future__ import annotations

import time
from typing import Any

SESSION_TTL_SECONDS = 30 * 60
MAX_SESSIONS = 200

_SESSIONS: dict[str, dict[str, Any]] = {}


def new_session_state() -> dict[str, Any]:
    return {
        "last_intent": None,
        "last_chart_type": None,
        "last_months": None,
        "last_category": None,
        "last_month": None,
        "active_goal_id": None,
        "active_goal_name": None,
        "last_amount": None,
        "last_contribution_amount": None,
        "pending_actions": {},
        "pending_confirmations": {},
        "purchase_plans": {},
        "contribution_states": {},
        "_last_seen": time.monotonic(),
    }


def _prune(now: float) -> None:
    expired = [
        session_id for session_id, state in _SESSIONS.items()
        if now - state["_last_seen"] > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        del _SESSIONS[session_id]
    while len(_SESSIONS) > MAX_SESSIONS:
        oldest = min(_SESSIONS, key=lambda sid: _SESSIONS[sid]["_last_seen"])
        del _SESSIONS[oldest]


def get_session(session_id: str) -> dict[str, Any]:
    """Devuelve el estado de la sesión, creándolo y renovando su actividad."""
    now = time.monotonic()
    state = _SESSIONS.get(session_id)
    if state is None:
        state = new_session_state()
        _SESSIONS[session_id] = state
    state["_last_seen"] = now
    _prune(now)
    return state


def prune_sessions() -> None:
    """Aplica TTL y límite de sesiones sin crear una sesión nueva."""
    _prune(time.monotonic())


def get_existing_session(session_id: str) -> dict[str, Any] | None:
    prune_sessions()
    state = _SESSIONS.get(session_id)
    if state is not None:
        state["_last_seen"] = time.monotonic()
    return state


def find_confirmation(action_id: str, session_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Busca una confirmación por sesión o, si no se indica, en el almacén."""
    if session_id is None:
        prune_sessions()
    candidates = (
        ((session_id, get_session(session_id)),) if session_id is not None
        else _SESSIONS.items()
    )
    for sid, state in candidates:
        data = state["pending_confirmations"].get(action_id)
        if data is not None:
            state["_last_seen"] = time.monotonic()
            return state, data
    return None


def clear() -> None:
    _SESSIONS.clear()
