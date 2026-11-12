"""Ciclo completo de acción A2UI: TransferForm → confirmación → dominio.

Recorre el camino real del producto sin dobles de herramientas:

1. El agente demo prepara un abono y lo publica como `TransferForm` en `ui_plan`.
2. El frontend responde con un evento de interfaz verificado en el servidor.
3. El dominio aplica la transferencia de forma atómica e idempotente.
4. El nuevo `ui_plan` refleja el abono y la reconciliación sigue en verde.

Las cifras no se simulan: las herramientas MCP son las implementaciones reales
sobre la base temporal `tmp_db`.
"""
import asyncio

import pytest

import tools.finance_tools as ft
from app.core import database
from app.core import reconcile as reconcile_mod
from app.schemas.api import ChatRequest, UIEventIn
from app.services.agent import loop, orchestrator as orch

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_savings_goals": ft.get_savings_goals_impl,
    "apply_savings_contribution": ft.apply_savings_contribution_impl,
}


async def real_tool(name: str, arguments: dict) -> dict:
    return await IMPLS[name](**arguments)


@pytest.fixture(autouse=True)
def patched_agent(tmp_db, monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "call", real_tool)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    monkeypatch.setattr(orch, "get_provider", lambda: None)
    monkeypatch.setattr(loop, "get_provider", lambda: None)
    orch.session_store.clear()
    yield
    orch.session_store.clear()


def _goal_cents(goal_name: str) -> tuple[int, int]:
    with database.db() as conn:
        row = conn.execute(
            "SELECT id, saved_amount_cents FROM savings_goals WHERE name=?",
            (goal_name,),
        ).fetchone()
    assert row is not None, goal_name
    return int(row["id"]), int(row["saved_amount_cents"])


def test_transfer_form_action_updates_domain_and_returns_a_new_ui_plan():
    goal_name = "Viaje a Japón"
    goal_id, saved_before = _goal_cents(goal_name)
    session_id = "ui-action-cycle"

    prepared = asyncio.run(orch.handle_chat(ChatRequest(
        message=f"Quiero abonar $500 a {goal_name}.", session_id=session_id,
    )))
    plan = loop.attach_ui_plan(prepared).ui_plan
    assert plan is not None
    form = next(
        component for component in plan["components"]
        if component["type"] == "TransferForm"
    )
    assert form["goal_id"] == goal_id
    assert form["amount"] == 500
    assert form["to_account"] == goal_name
    assert form["confirmation_token"]
    assert form["idempotency_key"]

    with database.db() as conn:
        transfers_before = conn.execute(
            "SELECT COUNT(*) FROM transactions"
            " WHERE goal_id=? AND type='transfer'",
            (goal_id,),
        ).fetchone()[0]

    event = UIEventIn(
        id="confirm-ui-action-cycle",
        type="savings_contribution_confirmed",
        payload={
            "goal_id": form["goal_id"],
            "amount": form["amount"],
            "confirmation_token": form["confirmation_token"],
            "idempotency_key": form["idempotency_key"],
        },
        trace_id=prepared.trace_id,
    )
    confirmed = asyncio.run(orch.handle_chat(ChatRequest(
        message="Confirmo el abono", ui_event=event, session_id=session_id,
    )))
    replay = asyncio.run(orch.handle_chat(ChatRequest(
        message="Doble clic",
        ui_event=event.model_copy(update={"id": "confirm-ui-action-cycle-replay"}),
        session_id=session_id,
    )))
    assert replay.model_dump() == confirmed.model_dump()
    updated_plan = loop.attach_ui_plan(confirmed).ui_plan
    assert updated_plan is not None
    kinds = [component["type"] for component in updated_plan["components"]]
    assert kinds == ["StatCard", "ProgressRing"]

    applied = updated_plan["components"][0]
    assert applied["title"] == "Abono aplicado"
    assert applied["value"] == "$500"
    assert goal_name in applied["hint"]
    progress = updated_plan["components"][1]
    assert progress["label"] == goal_name
    assert progress["value"] == pytest.approx(19.3)
    assert progress["target_label"] == "$45,000"

    # Dominio: el ahorro sube exactamente $500 (50,000 centavos) y queda una
    # sola transferencia con sus dos piernas.
    _, saved_after = _goal_cents(goal_name)
    assert saved_after == saved_before + 50_000
    with database.db() as conn:
        transfer = conn.execute(
            "SELECT id, amount_cents FROM transactions"
            " WHERE goal_id=? AND type='transfer'"
            " ORDER BY id DESC LIMIT 1",
            (goal_id,),
        ).fetchone()
        assert transfer is not None
        assert transfer["amount_cents"] == 50_000
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE goal_id=? AND type='transfer'",
            (goal_id,),
        ).fetchone()[0]
        assert count == transfers_before + 1
        legs = conn.execute(
            "SELECT amount_cents FROM transfer_legs WHERE transaction_id=?",
            (transfer["id"],),
        ).fetchall()
        assert sum(int(leg["amount_cents"]) for leg in legs) == 50_000
        report = reconcile_mod.reconcile(conn)

    assert report["ok"] is True
    assert report["failures"] == 0
    assert report["invariant_count"] == 13


def test_contribution_to_non_first_goal_shows_that_goal_in_progress_ring():
    """Regresión: el ProgressRing debe mostrar la meta abonada, no `goals[0]`."""
    first_goal_name = "Fondo de emergencia"
    goal_name = "Enganche del auto"
    goal_id, saved_before = _goal_cents(goal_name)
    _, first_saved_before = _goal_cents(first_goal_name)
    session_id = "ui-action-non-first-goal"

    prepared = asyncio.run(orch.handle_chat(ChatRequest(
        message=f"Quiero abonar $500 a {goal_name}.", session_id=session_id,
    )))
    plan = loop.attach_ui_plan(prepared).ui_plan
    assert plan is not None
    form = next(
        component for component in plan["components"]
        if component["type"] == "TransferForm"
    )
    assert form["goal_id"] == goal_id
    assert form["to_account"] == goal_name

    event = UIEventIn(
        id="confirm-non-first-goal",
        type="savings_contribution_confirmed",
        payload={
            "goal_id": form["goal_id"],
            "amount": form["amount"],
            "confirmation_token": form["confirmation_token"],
            "idempotency_key": form["idempotency_key"],
        },
        trace_id=prepared.trace_id,
    )
    confirmed = asyncio.run(orch.handle_chat(ChatRequest(
        message="Confirmo el abono", ui_event=event, session_id=session_id,
    )))
    updated_plan = loop.attach_ui_plan(confirmed).ui_plan
    assert updated_plan is not None
    assert [c["type"] for c in updated_plan["components"]] == [
        "StatCard", "ProgressRing",
    ]

    applied = updated_plan["components"][0]
    assert applied["title"] == "Abono aplicado"
    assert applied["value"] == "$500"
    assert goal_name in applied["hint"]

    progress = updated_plan["components"][1]
    assert progress["label"] == goal_name
    assert progress["label"] != first_goal_name
    assert progress["value"] == pytest.approx(51.1)
    assert progress["target_label"] == "$45,000"

    # El dominio abona la meta B y no toca la meta A.
    _, saved_after = _goal_cents(goal_name)
    assert saved_after == saved_before + 50_000
    _, first_saved_after = _goal_cents(first_goal_name)
    assert first_saved_after == first_saved_before
    with database.db() as conn:
        report = reconcile_mod.reconcile(conn)
    assert report["ok"] is True
    assert report["failures"] == 0
