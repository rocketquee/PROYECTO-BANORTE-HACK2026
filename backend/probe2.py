import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
import app.services.agent.orchestrator as orch
import tools.finance_tools as ft
from app.core import database, seed
from app.schemas.api import ChatRequest

db_file = os.path.join(tempfile.gettempdir(), "qa_probe3.db")
if os.path.exists(db_file):
    os.remove(db_file)
database.DB_PATH = db_file
with database.db() as conn:
    seed.init_db(conn)

async def fake_call(name, args):
    return await getattr(ft, f"{name}_impl")(**args)

orch.mcp_client.call = fake_call

r = asyncio.run(orch.demo_response(ChatRequest(message="Muéstrame mis gastos por categoría en barras")))
spec = r.ui[0].model_dump()
print("R1 chart_type:", spec.get("chart_type"), "| type:", spec.get("type"))

r2 = asyncio.run(orch.demo_response(ChatRequest(message="¿Qué pagos fijos tengo?")))
items = r2.ui[0].model_dump()["items"]
print("R7 items:", len(items), "| said:", r2.message.split("Detecté ")[1][:2])
descs = [i["title"].split(" · ")[0] for i in items]
print("R7 includes Regalo Navidad:", any("Regalo" in d for d in descs))
total = sum(float(i["title"].split("$")[1].split("/")[0].replace(",", "")) for i in items)
print("R7 sum of items:", round(total, 2))
