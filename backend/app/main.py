"""Banorte AI Finanzas — FastAPI backend (prototype, synthetic data only)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core import config, database
from app.services.mcp_client import mcp_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_dotenv()
    database.ensure_db()
    try:
        await mcp_client.start()
        print(f"[mcp] conectado — {len(mcp_client.tools)} herramientas descubiertas: "
              f"{[t.name for t in mcp_client.tools]}")
    except Exception as exc:  # noqa: BLE001 - report, don't crash the API
        print(f"[mcp] ERROR al iniciar el servidor MCP: {exc}")
    yield
    await mcp_client.stop()


app = FastAPI(
    title="Banorte AI Finanzas API",
    version="0.1.0",
    description="Prototipo educativo: agente financiero + MCP + interfaces dinámicas. "
                "Datos sintéticos; no afiliado a Banorte.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
