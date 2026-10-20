"""Probe: reproduce user-reported agent findings. Prints message + components."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))

import app.services.agent.orchestrator as orch  # noqa: E402
import tools.finance_tools as ft  # noqa: E402
from app.core import database, seed  # noqa: E402
from app.schemas.api import ChatRequest  # noqa: E402

db_file = os.path.join(tempfile.gettempdir(), "qa_probe2.db")
if os.path.exists(db_file):
    os.remove(db_file)
database.DB_PATH = db_file
with database.db() as conn:
    seed.init_db(conn)


async def fake_call(name, args):
    impl = getattr(ft, f"{name}_impl", None)
    if impl is None:
        raise RuntimeError(f"tool {name} has no impl")
    return await impl(**args)


orch.mcp_client.call = fake_call

PHRASES = [
    "Muéstrame mis gastos por categoría en barras",
    "Enséñame mi línea del tiempo de movimientos",
    "¿Cuándo me cae la nómina?",
    "¿Cuánto recibí de aguinaldo?",
    "¿Eres una persona real?",
    "¿Eres de Banorte?",
    "¿Tengo algún cobro duplicado?",
    "¿Tengo cargos inusuales?",
    "Compara mis gastos de septiembre contra octubre",
    "¿Qué pagos fijos tengo?",
    "¿Cuánto llevo gastado en comida?",
    "¿Cómo voy con mi presupuesto?",
    "Analiza mis gastos de este mes",
    "¿Cuál es mi saldo?",
]

for phrase in PHRASES:
    r = asyncio.run(orch.demo_response(ChatRequest(message=phrase)))
    comps = [u.type for u in r.ui]
    print("=" * 70)
    print(f"FRASE: {phrase}")
    print(f"MSG: {r.message}")
    for u in r.ui:
        payload = u.model_dump(exclude_none=True)
        for k, v in payload.items():
            if k in ("title", "period", "conclusion", "items", "series", "rows", "categories"):
                print(f"  [{u.type}] {k}={str(v)[:400]}")
    print(f"COMPONENTES: {comps}")
