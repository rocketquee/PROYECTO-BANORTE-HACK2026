"""Safe structured logging for application events."""
import json
import logging
import re
from datetime import datetime, timezone


_SAFE_EVENT = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_SAFE_TRACE_ID = re.compile(r"^[a-f0-9]{32}$")
_SAFE_FIELDS = (
    "trace_id",
    "step",
    "attempt",
    "tool",
    "tool_count",
    "error_type",
    "event_type",
    "service_count",
    "input_length",
)


class StructuredJsonFormatter(logging.Formatter):
    """Emit stable JSON fields while excluding arbitrary LogRecord extras."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": message if _SAFE_EVENT.fullmatch(message) else "log_event",
        }
        for field in _SAFE_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, (str, int, float, bool)):
                if field == "trace_id" and (
                    not isinstance(value, str) or not _SAFE_TRACE_ID.fullmatch(value)
                ):
                    continue
                event[field] = value
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def configure_application_logging() -> None:
    logger = logging.getLogger("banorte")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "_banorte_json", False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())
    handler._banorte_json = True
    logger.addHandler(handler)
