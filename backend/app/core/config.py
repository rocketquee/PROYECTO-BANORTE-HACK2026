"""Central configuration. All secrets come from environment variables; never commit them."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
ROOT_DIR = BASE_DIR.parent                       # project root
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "banorte.db"
MCP_SERVER_PATH = ROOT_DIR / "mcp-server" / "server.py"

# AI provider: "demo" (no API key needed) | "openai" | "anthropic"
AI_PROVIDER = os.getenv("AI_PROVIDER", "demo")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

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
