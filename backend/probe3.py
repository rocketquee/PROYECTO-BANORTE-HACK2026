import asyncio, os, sys, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
import app.services.agent.orchestrator as orch
import tools.finance_tools as ft
from app.core import database, seed
from app.schemas.api import ChatRequest

db_file = os.path.join(tempfile.gettempdir(), "qa_probe4.db")
if os.path.exists(db_file):
    os.remove(db_file)
database.DB_PATH = db_file
with database.db() as conn:
    seed.init_db(conn)

async def fake_call(name, args):
    return await getattr(ft, f"{name}_impl")(**args)

orch.mcp_client.call = fake_call

r = asyncio.run(orch.demo_response(ChatRequest(message="¿Qué pagos fijos tengo?")))
print("R07 MSG:", repr(r.message))
print("R07 items:", len(r.ui[0].model_dump()["items"]))

r2 = asyncio.run(orch.demo_response(ChatRequest(message="¿Cuánto llevo gastado en comida?")))
spec = r2.ui[0].model_dump()
print("R10 cats:", [s["category"] for s in spec["series"]], "| title:", repr(spec["title"]))

r3 = asyncio.run(orch.demo_response(ChatRequest(message="¿Tengo cargos inusuales?")))
print("R05 anomalies:", [i["title"] for i in r3.ui[0].model_dump()["items"]])

with database.db() as conn:
    for mo in range(1, 11):
        b = ft.__dict__
    from app.services import finance
    for mo in (7, 8, 9, 10):
        b = finance.budget_overview(conn, 2026, mo)
        print(f"month {mo}: income={b['income']} spent={b['total_spent']} avail={b['available']}")
