"""Central configuration. All secrets come from environment variables; never commit them."""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
ROOT_DIR = BASE_DIR.parent                       # project root
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("BANORTE_DB_PATH", str(DATA_DIR / "banorte.db")))
MCP_SERVER_PATH = ROOT_DIR / "mcp-server" / "server.py"

# AI provider: "demo" (no API key needed) | "openai" | "anthropic"
AI_PROVIDER = os.getenv("AI_PROVIDER", "demo")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "6"))
AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "1"))
AGENT_RETRY_DELAY_SECONDS = float(os.getenv("AGENT_RETRY_DELAY_SECONDS", "0.2"))
AGENT_TOOL_TIMEOUT_SECONDS = float(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "10"))
AGENT_MAX_COST_USD = float(os.getenv("AGENT_MAX_COST_USD", "0.05"))

_DEFAULT_TOKEN_COSTS = {
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.00000060},
    "claude-sonnet-4-20250514": {"input": 0.000003, "output": 0.000015},
}


def parse_token_costs(raw: str | None) -> dict[str, dict[str, float]]:
    """Precio por token de entrada/salida por modelo, en USD."""
    if not raw:
        return {model: dict(costs) for model, costs in _DEFAULT_TOKEN_COSTS.items()}
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ValueError("AGENT_TOKEN_COSTS debe ser JSON válido.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("AGENT_TOKEN_COSTS debe ser un objeto modelo → precios.")
    costs: dict[str, dict[str, float]] = {}
    for model, value in parsed.items():
        if not isinstance(value, dict):
            raise ValueError(f"AGENT_TOKEN_COSTS.{model} debe ser un objeto.")
        try:
            input_cost = float(value["input"])
            output_cost = float(value["output"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"AGENT_TOKEN_COSTS.{model} requiere 'input' y 'output' numéricos."
            ) from exc
        if input_cost < 0 or output_cost < 0:
            raise ValueError(f"AGENT_TOKEN_COSTS.{model} no puede ser negativo.")
        costs[str(model)] = {"input": input_cost, "output": output_cost}
    return costs


AGENT_TOKEN_COSTS = parse_token_costs(os.getenv("AGENT_TOKEN_COSTS"))

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Developer mode: enables API docs (/docs) and technical UI details.
# Disabled by default; never toggleable from the public interface.
DEV_MODE = os.getenv("DEV_MODE", "") in ("1", "true", "yes")


def load_dotenv() -> None:
    """Minimal .env loader (no external dependency). Values already set in the
    environment take precedence."""
    for name in (ROOT_DIR / ".env", BASE_DIR / ".env"):
        if not name.exists():
            continue
        for line in name.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    converters = {
        "AI_PROVIDER": ("AI_PROVIDER", str),
        "OPENAI_API_KEY": ("OPENAI_API_KEY", str),
        "OPENAI_MODEL": ("OPENAI_MODEL", str),
        "OPENAI_BASE_URL": ("OPENAI_BASE_URL", str),
        "ANTHROPIC_API_KEY": ("ANTHROPIC_API_KEY", str),
        "ANTHROPIC_MODEL": ("ANTHROPIC_MODEL", str),
        "AI_TEMPERATURE": ("AI_TEMPERATURE", float),
        "AI_TIMEOUT_SECONDS": ("AI_TIMEOUT_SECONDS", float),
        "AGENT_MAX_STEPS": ("AGENT_MAX_STEPS", int),
        "AGENT_MAX_RETRIES": ("AGENT_MAX_RETRIES", int),
        "AGENT_RETRY_DELAY_SECONDS": ("AGENT_RETRY_DELAY_SECONDS", float),
        "AGENT_TOOL_TIMEOUT_SECONDS": ("AGENT_TOOL_TIMEOUT_SECONDS", float),
        "AGENT_MAX_COST_USD": ("AGENT_MAX_COST_USD", float),
        "AGENT_TOKEN_COSTS": ("AGENT_TOKEN_COSTS", parse_token_costs),
        "FRONTEND_ORIGIN": ("FRONTEND_ORIGIN", str),
        "DEV_MODE": ("DEV_MODE", lambda value: value.lower() in ("1", "true", "yes")),
    }
    for env_name, (setting_name, converter) in converters.items():
        if env_name in os.environ:
            globals()[setting_name] = converter(os.environ[env_name])
