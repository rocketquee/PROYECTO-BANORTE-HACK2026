"""Guardia estática: prohibido flotante en las rutas del dinero (D1).

Regla aprobada: la conversión pesos↔centavos vive **solo** en
`app.core.money`. Esta prueba recorre el árbol de sintaxis de los módulos de
dinero y falla si aparece:

1. una llamada a `round(` — la normalización y el redondeo solo ocurren en
   `money` (los porcentajes usan `money.pct`, los importes `money.boundary`);
2. una conversión de centavos escrita a mano (aritmética con el literal
   `100` o `0.01` fuera de `money.py`);
3. una columna de dinero de la base que no sea `INTEGER` de centavos.

`float(` se permite únicamente como parsing de texto y paso directo de datos
de herramienta (no es aritmética de dinero); la semilla queda fuera del
alcance porque genera datos de demostración y entrega sus importes al libro
exclusivamente vía `money.to_cents` (lo verifica la regla 3).
"""
import ast
import sqlite3
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

# Módulos por donde circula dinero (capa de dominio, API y herramientas).
MONEY_MODULES = [
    BACKEND_DIR / "app" / "services" / "finance.py",
    BACKEND_DIR / "app" / "services" / "domain.py",
    BACKEND_DIR / "app" / "services" / "savings.py",
    BACKEND_DIR / "app" / "services" / "credit.py",
    BACKEND_DIR / "app" / "services" / "agent" / "composer.py",
    BACKEND_DIR / "app" / "services" / "agent" / "orchestrator.py",
    BACKEND_DIR / "app" / "api" / "routes.py",
    ROOT_DIR / "mcp-server" / "tools" / "finance_tools.py",
]

CONVERSION_LITERALS = {100, 100.0, 0.01}


def _calls(node, name):
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) \
                and child.func.id == name:
            yield child


def _conversion_literals(node):
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, (ast.Mult, ast.Div)):
            for operand in (child.left, child.right):
                if isinstance(operand, ast.Constant) and operand.value in CONVERSION_LITERALS:
                    yield child


def test_no_round_calls_outside_money_module():
    offenders = []
    for path in MONEY_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree, "round"):
            offenders.append(f"{path.name}:{call.lineno}")
    assert not offenders, (
        "round( prohibido fuera de app/core/money.py; usa money.boundary / "
        f"money.pct / money.round_half_up: {offenders}"
    )


def test_no_hand_written_cent_conversions():
    offenders = []
    for path in MONEY_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _conversion_literals(tree):
            offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "conversión de centavos escrita a mano (×/÷ 100 o 0.01); la única "
        f"conversión permitida es app/core/money.py: {offenders}"
    )


def test_money_columns_are_integer_cents(tmp_db):
    """Toda columna de dinero en la base es INTEGER de centavos."""
    money_columns = {
        "transactions": ["amount_cents"],
        "accounts": ["balance_cents"],
        "cards": ["balance_cents", "credit_limit_cents"],
        "savings_goals": ["target_amount_cents", "saved_amount_cents"],
        "budgets": ["monthly_limit_cents"],
    }
    conn = sqlite3.connect(tmp_db)
    try:
        for table, columns in money_columns.items():
            types = {r[1]: (r[2] or "").upper()
                     for r in conn.execute(f"PRAGMA table_info({table})")}
            for column in columns:
                assert types.get(column) == "INTEGER", (
                    f"{table}.{column} debe ser INTEGER de centavos; es {types.get(column)}"
                )
    finally:
        conn.close()


def test_money_module_is_the_only_converter():
    """money.py existe y expone el contrato completo de conversión."""
    from app.core import money  # noqa: F401
    for name in ("to_cents", "to_pesos", "boundary", "difference", "round_half_up",
                 "apply_rate", "monthly_rate", "pct", "split_evenly"):
        assert hasattr(money, name), f"falta money.{name}"
