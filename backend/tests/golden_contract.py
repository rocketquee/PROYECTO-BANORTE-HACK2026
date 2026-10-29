"""Línea base dorada del contrato observable.

Requisito de D1 (centavos): **antes** de migrar, capturar las respuestas de
todos los endpoints REST y de todas las herramientas MCP, y demostrar que
después son idénticas. Este módulo captura esa línea base de forma
determinista y la normaliza.

Determinismo: se fija la fecha de referencia de la demo y se normalizan solo
los campos volátiles conocidos (`created_at`, `updated_at`). Todo lo demás se
compara literal, de modo que la comparación detecta cualquier deriva real.

Uso:
    python -m tests.golden_contract --write    # regenera la línea base
    python -m tests.golden_contract            # compara contra la línea base
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
for _path in (str(BACKEND_DIR), str(ROOT_DIR / "mcp-server")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

BASELINE_PATH = Path(__file__).resolve().parent / "golden" / "api-baseline.json"

# Campos que cambian por reloj y no por lógica: se normalizan.
VOLATILE_KEYS = {"created_at", "updated_at"}
VOLATILE_VALUE = "<normalizado>"

# Claves de idempotencia fijas: reproducibles entre corridas.
IDEMPOTENCY_KEYS = {
    "mcp_create": "00000000-0000-4000-8000-000000000001",
    "mcp_contribution": "00000000-0000-4000-8000-000000000002",
    "rest_transfer": "00000000-0000-4000-8000-000000000003",
}

# Cambios de contrato APROBADOS de forma explícita (no son regresiones).
# ledger-v2 (decisión de centavos): la tabla de amortización ahora se calcula
# en centavos con ROUND_HALF_UP y la última cuota absorbe el residuo para que
# Σ capital = monto exacto. El comportamiento flotante anterior derivaba
# ±centavos en saldos intermedios y no cerraba la operación.
APPROVED_RULE_CHANGES = {
    "POST /credit/simulate.schedule",
    "POST /credit/simulate.total_interest",
    "POST /credit/simulate.total_paid",
    "MCP calculate_credit_simulation.schedule",
    "MCP calculate_credit_simulation.total_interest",
    "MCP calculate_credit_simulation.total_paid",
    "MCP compare_credit_terms.terms",
}

DEMO_TODAY = "2026-10-25"


def normalize(value):
    """Normaliza campos volátiles de forma recursiva."""
    if isinstance(value, dict):
        return {
            key: (VOLATILE_VALUE if key in VOLATILE_KEYS else normalize(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def _rounded(value):
    """Redondea a 2 decimales para que la comparación sea sobre dinero, no sobre ruido."""
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def _rest_calls(client):
    """Todas las llamadas REST de solo lectura, con parámetros explícitos."""
    return {
        "GET /health": lambda: client.get("/api/health").json(),
        "GET /dashboard": lambda: client.get("/api/dashboard", params={"month": "2026-10"}).json(),
        "GET /transactions": lambda: client.get(
            "/api/transactions", params={"limit": 5}).json(),
        "GET /transactions?type=transfer": lambda: client.get(
            "/api/transactions", params={"type": "transfer", "limit": 5}).json(),
        "GET /transactions?category=Supermercado": lambda: client.get(
            "/api/transactions", params={"category": "Supermercado", "limit": 5}).json(),
        "GET /analytics/trend": lambda: client.get(
            "/api/analytics/trend", params={"months": 6}).json(),
        "GET /goals": lambda: client.get("/api/goals").json(),
        "GET /budget": lambda: client.get("/api/budget", params={"month": "2026-10"}).json(),
        "GET /ui-schema": lambda: client.get("/api/ui-schema").json(),
        "POST /credit/simulate": lambda: client.post(
            "/api/credit/simulate",
            json={"amount": 50_000, "months": 24, "annual_rate": 15.9,
                  "method": "frances"}).json(),
    }


async def _mcp_calls():
    """Todas las herramientas MCP de solo lectura."""
    from tools import finance_tools as ft

    return {
        "get_balance": lambda: ft.get_balance_impl(),
        "get_transactions": lambda: ft.get_transactions_impl(limit=5),
        "get_cards": lambda: ft.get_cards_impl(),
        "get_savings_goals": lambda: ft.get_savings_goals_impl(),
        "get_monthly_summary": lambda: ft.get_monthly_summary_impl(2026, 10),
        "get_budgets": lambda: ft.get_budgets_impl(2026, 10),
        "get_spending_trend": lambda: ft.get_spending_trend_impl(months=6),
        "compare_months": lambda: ft.compare_months_impl("2026-09", "2026-10"),
        "get_weekly_spending": lambda: ft.get_weekly_spending_impl(weeks=4),
        "detect_recurring_charges": lambda: ft.detect_recurring_charges_impl(),
        "detect_duplicates": lambda: ft.detect_duplicates_impl(),
        "detect_anomalies": lambda: ft.detect_anomalies_impl(),
        "analyze_spending": lambda: ft.analyze_spending_impl(year=2026, month=10),
        "project_savings": lambda: ft.project_savings_impl(3_000, 45_000, already_saved=8_200),
        "compare_credit_terms": lambda: ft.compare_credit_terms_impl(50_000),
        "budget_vs_actual": lambda: ft.budget_vs_actual_impl(2026, 10),
        "calculate_credit_simulation": lambda: ft.calculate_credit_simulation_impl(
            50_000, 24, 15.9, "frances"),
    }


async def capture() -> dict:
    """Ejecuta todas las llamadas observables y devuelve el mapa normalizado."""
    import os
    import tempfile

    os.environ["BANORTE_DEMO_TODAY"] = DEMO_TODAY
    os.environ["AI_PROVIDER"] = "demo"          # el respaldo es determinista
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)

    from app.core import database
    from app.core import seed as seed_mod

    # Jamás tocar la base del repositorio: la corrida usa una base temporal.
    tmp_db = Path(tempfile.gettempdir()) / f"golden_{os.getpid()}_{id(object())}.db"
    original_db_path = database.DB_PATH
    database.DB_PATH = tmp_db

    snapshot: dict = {"demo_today": DEMO_TODAY}

    with database.db() as conn:
        seed_mod.init_db(conn)

    # 1. Lecturas REST y MCP primero: no cambian el estado.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        for name, call in _rest_calls(client).items():
            snapshot[name] = call()

        for name, call in (await _mcp_calls()).items():
            snapshot[f"MCP {name}"] = await call()

        # 2. Escrituras al final, en orden fijo, con claves fijas.
        from tools import finance_tools as ft

        created = await ft.create_savings_goal_impl(
            name="Meta dorada", target_amount=12_000, confirm=True,
            idempotency_key=IDEMPOTENCY_KEYS["mcp_create"])
        snapshot["MCP create_savings_goal"] = created

        goal_id = created["goal"]["id"]
        snapshot["MCP update_savings_goal"] = await ft.update_savings_goal_impl(
            goal_id, target_amount=15_000, confirm=True)
        snapshot["MCP apply_savings_contribution"] = await ft.apply_savings_contribution_impl(
            goal_id, 1_500, confirm=True,
            idempotency_key=IDEMPOTENCY_KEYS["mcp_contribution"])

        snapshot["POST /goals"] = client.post(
            "/api/goals", json={"name": "Meta REST dorada", "target_amount": 9_000}).json()
        snapshot["PATCH /goals/{id}"] = client.patch(
            f"/api/goals/{goal_id}", json={"target_amount": 16_000}).json()
        snapshot["POST /goals/{id}/transfers"] = client.post(
            f"/api/goals/{goal_id}/transfers",
            json={"amount": 500, "direction": "account_to_goal",
                  "idempotency_key": IDEMPOTENCY_KEYS["rest_transfer"]}).json()
        snapshot["POST /budget/update"] = client.post(
            "/api/budget/update",
            json={"category": "Supermercado", "monthly_limit": 7_000}).json()
        snapshot["POST /agent/chat"] = client.post(
            "/api/agent/chat",
            json={"message": "¿cuál es mi saldo?", "conversation_id": None}).json()

        # 3. Estado final: los saldos derivados tras las escrituras.
        snapshot["GET /dashboard (final)"] = client.get(
            "/api/dashboard", params={"month": "2026-10"}).json()
        snapshot["GET /goals (final)"] = client.get("/api/goals").json()

    # Restaura la ruta real y borra la base temporal.
    database.DB_PATH = original_db_path
    tmp_db.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(str(tmp_db) + suffix).unlink(missing_ok=True)

    return normalize(_rounded(snapshot))


def write_baseline(path: Path = BASELINE_PATH) -> Path:
    import asyncio

    path.parent.mkdir(parents=True, exist_ok=True)
    data = asyncio.run(capture())
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")
    return path


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _diff(expected: dict, actual: dict, prefix: str = "") -> list[str]:
    problems: list[str] = []
    for key in sorted(set(expected) | set(actual)):
        path = f"{prefix}{key}"
        if key not in expected:
            problems.append(f"{path}: apareció (no estaba en la línea base)")
        elif key not in actual:
            problems.append(f"{path}: desapareció")
        elif isinstance(expected[key], dict) and isinstance(actual[key], dict):
            problems.extend(_diff(expected[key], actual[key], f"{path}."))
        elif expected[key] != actual[key]:
            problems.append(f"{path}: {expected[key]!r} ≠ {actual[key]!r}")
    return problems


def main(argv=None) -> int:
    import asyncio

    parser = argparse.ArgumentParser(description="Línea base dorada del contrato observable.")
    parser.add_argument("--write", action="store_true", help="regenera la línea base")
    args = parser.parse_args(argv)

    if args.write:
        path = write_baseline()
        print(f"línea base escrita: {path}")
        return 0

    expected = load_baseline()
    actual = asyncio.run(capture())
    problems = _diff(expected, actual)
    if problems:
        print(f"DIFERENCIAS ({len(problems)}):")
        for item in problems[:40]:
            print("  -", item)
        return 1
    print(f"contrato idéntico a la línea base ({len(expected)} grupos observados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
