"""Etapa 5C: generated evaluation, holdout baseline and regression gate."""
import ast
import asyncio
import json
from pathlib import Path

import pytest

import app.services.agent.orchestrator as orch
import tools.finance_tools as ft
from app.core import database
from app.schemas.api import ChatRequest
from app.services import finance
from app.services.mcp_catalog import MCP_ALLOWED_TOOLS

from eval_harness import (
    SimProvider,
    build_cases,
    run_case,
    summarize,
)

BASELINE_PATH = Path(__file__).resolve().parent / "eval_baseline.json"

IMPLS = {
    "get_balance": ft.get_balance_impl,
    "get_monthly_summary": ft.get_monthly_summary_impl,
    "get_budgets": ft.get_budgets_impl,
    "analyze_spending": ft.analyze_spending_impl,
    "get_transactions": ft.get_transactions_impl,
    "get_cards": ft.get_cards_impl,
    "get_savings_goals": ft.get_savings_goals_impl,
    "get_spending_trend": ft.get_spending_trend_impl,
    "get_weekly_spending": ft.get_weekly_spending_impl,
    "detect_recurring_charges": ft.detect_recurring_charges_impl,
    "detect_duplicates": ft.detect_duplicates_impl,
    "detect_anomalies": ft.detect_anomalies_impl,
    "compare_months": ft.compare_months_impl,
    "project_savings": ft.project_savings_impl,
    "calculate_credit_simulation": ft.calculate_credit_simulation_impl,
    "compare_credit_terms": ft.compare_credit_terms_impl,
    "budget_vs_actual": ft.budget_vs_actual_impl,
    "create_savings_goal": ft.create_savings_goal_impl,
    "update_savings_goal": ft.update_savings_goal_impl,
    "apply_savings_contribution": ft.apply_savings_contribution_impl,
    "set_budget_limit": ft.set_budget_limit_impl,
}


async def fake_call(name: str, args: dict) -> dict:
    return await IMPLS[name](**args)


@pytest.fixture(autouse=True)
def patched_agent(tmp_db, monkeypatch):
    monkeypatch.setattr(orch.mcp_client, "call", fake_call)
    monkeypatch.setattr(orch.mcp_client, "session", object())
    specs = [
        {"name": name, "description": name,
         "input_schema": {"type": "object", "properties": {}}}
        for name in sorted(MCP_ALLOWED_TOOLS)
    ]
    monkeypatch.setattr(orch.mcp_client, "tool_specs", lambda: specs)
    orch.session_store.clear()
    yield
    orch.session_store.clear()


def _ask_for(mode: str, monkeypatch):
    provider = SimProvider()
    if mode == "sim":
        monkeypatch.setattr(orch, "get_provider", lambda: provider)
    else:
        monkeypatch.setattr(orch, "get_provider", lambda: None)

    async def ask(message: str, case_id: str):
        request = ChatRequest(message=message, session_id=f"eval-{case_id}")
        if mode == "rules":
            return await orch.demo_response(request, "trace-eval")
        return await orch.handle_chat(request)

    return ask


def _assert_gate(report: dict, mode: str) -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))[mode]
    assert report["overall"]["approval"] >= baseline["overall"], (
        f"{mode}: aprobación global {report['overall']['approval']:.3f} "
        f"< línea base {baseline['overall']:.3f}\n{_format_report(report)}"
    )
    assert report["holdout"]["approval"] >= baseline["holdout"], (
        f"{mode}: holdout {report['holdout']['approval']:.3f} "
        f"< línea base {baseline['holdout']:.3f}\n{_format_report(report)}"
    )


def _format_report(report: dict) -> str:
    lines = [f"global {report['overall']['approved']}/{report['overall']['total']} "
             f"({report['overall']['approval']:.1%}) "
             f"latencia media {report['overall']['avg_latency_ms']:.1f} ms "
             f"cifras bloqueadas {report['overall']['blocked_figures']}",
             f"holdout {report['holdout']['approved']}/{report['holdout']['total']} "
             f"({report['holdout']['approval']:.1%})",
             "categorías:"]
    for category, metrics in report["by_category"].items():
        lines.append(f"  - {category}: {metrics['approved']}/{metrics['total']} "
                     f"({metrics['approval']:.1%}) "
                     f"{metrics['avg_latency_ms']:.1f} ms "
                     f"bloqueadas {metrics['blocked_figures']}")
    lines.append("entidades:")
    for entity, metrics in report["by_entity"].items():
        lines.append(f"  - {entity}: {metrics['approved']}/{metrics['total']} "
                     f"({metrics['approval']:.1%}) "
                     f"{metrics['avg_latency_ms']:.1f} ms "
                     f"bloqueadas {metrics['blocked_figures']}")
    failed = [result for result in report["results"] if not result["approved"]]
    if failed:
        lines.append("fallos:")
        for result in failed:
            lines.append(f"  - {result['mode']}:{result['case_id']} "
                         f"[{result['category']}/{result['entity']}] "
                         f"{result['reason']} figs={result['unsupported_figures']} "
                         f"msg={result['message']!r}")
    return "\n".join(lines)


@pytest.mark.parametrize("mode", ["rules", "sim"])
def test_generated_evaluation_meets_baseline(mode, monkeypatch):
    cases = build_cases()
    ask = _ask_for(mode, monkeypatch)
    results = [asyncio.run(run_case(case, ask, mode)) for case in cases]
    report = summarize(results)

    print(f"\nEvaluación modo {mode}\n{_format_report(report)}")
    _assert_gate(report, mode)


def test_report_has_category_and_entity_breakdown(monkeypatch):
    cases = build_cases()
    ask = _ask_for("rules", monkeypatch)
    report = summarize([asyncio.run(run_case(case, ask, "rules")) for case in cases])

    assert set(report["by_category"]) >= {
        "goals", "categories", "accounts", "followups", "ambiguity",
        "honesty", "security", "colloquial", "comparisons", "writes",
        "ui_selection", "typos",
    }
    assert report["by_entity"]
    assert report["holdout"]["total"] > 0


def test_orchestrator_has_no_seed_entity_literals(tmp_db):
    with database.db() as conn:
        names = {goal["name"] for goal in finance.list_goals(conn)}
        names.update(finance.category_taxonomy(conn))
    source = Path(orch.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    vocabulary_nodes: set[int] = set()
    vocabulary = {
        "CATEGORY_SYNONYMS", "CATEGORY_GROUPS",  # lenguaje, no datos de la demo
        "_NAV_ROUTES", "NAV_SECTION_LABELS",      # navegación, no respuestas
    }
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id in vocabulary
               for target in node.targets):
            vocabulary_nodes.update(id(child) for child in ast.walk(node))
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in vocabulary_nodes
    }
    leaked = sorted(name for name in names if name in literals)
    assert not leaked, f"nombres de la semilla codificados en el orquestador: {leaked}"
