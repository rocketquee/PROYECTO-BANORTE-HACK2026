"""Banorte AI Finanzas — FastAPI backend (prototype, synthetic data only).

Security defaults:
- API docs (/docs, /redoc, /openapi.json) disabled unless DEV_MODE=1.
- Generic error messages for users; details only in the server log.
- No server/version headers leaked in responses.
- Logs never contain user message content.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core import config, database
from app.services.mcp_client import mcp_client

logger = logging.getLogger("banorte")
logging.basicConfig(level=logging.INFO)

GENERIC_ERROR = "No pude hacer eso. ¿Lo intentamos de otra forma?"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.load_dotenv()
    database.ensure_db()
    try:
        await mcp_client.start()
        logger.info("Servidor de herramientas conectado (%s disponibles).",
                    len(mcp_client.tools))
    except Exception as exc:  # noqa: BLE001 - report, don't crash the API
        logger.error("Error al iniciar el servidor de herramientas: %s", exc)
    yield
    await mcp_client.stop()


docs_url = "/docs" if config.DEV_MODE else None
redoc_url = "/redoc" if config.DEV_MODE else None
openapi_url = "/openapi.json" if config.DEV_MODE else None

app = FastAPI(
    title="Banorte AI Finanzas API",
    version="0.1.0",
    description="Prototipo educativo con datos sintéticos; no afiliado a Banorte.",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def hide_server_header(request: Request, call_next):
    response = await call_next(request)
    if "server" in response.headers:
        del response.headers["server"]
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    # Details go to the log only; the user sees a friendly, non-technical message.
    logger.error("Error interno en %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": GENERIC_ERROR})


app.include_router(router)
