"""Central configuration. All secrets come from environment variables; never commit them."""
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
        "FRONTEND_ORIGIN": ("FRONTEND_ORIGIN", str),
        "DEV_MODE": ("DEV_MODE", lambda value: value.lower() in ("1", "true", "yes")),
    }
    for env_name, (setting_name, converter) in converters.items():
        if env_name in os.environ:
            globals()[setting_name] = converter(os.environ[env_name])
