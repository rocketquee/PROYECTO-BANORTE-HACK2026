import json
import logging

from app.core.structured_logging import StructuredJsonFormatter


def test_structured_logs_include_trace_and_exclude_unapproved_fields():
    record = logging.LogRecord(
        name="banorte.agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="agent_request_received",
        args=(),
        exc_info=None,
    )
    record.trace_id = "abcdef0123456789abcdef0123456789"
    record.input_length = 34
    record.user_message = "mi NIP es 9876"
    record.password = "no-debe-registrarse"

    event = json.loads(StructuredJsonFormatter().format(record))

    assert event["event"] == "agent_request_received"
    assert event["trace_id"] == "abcdef0123456789abcdef0123456789"
    assert event["input_length"] == 34
    assert "user_message" not in event
    assert "password" not in event
    assert "9876" not in json.dumps(event)


def test_structured_logs_sanitize_untrusted_event_and_trace_values():
    record = logging.LogRecord(
        name="banorte.agent",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="El NIP del usuario es 9876",
        args=(),
        exc_info=None,
    )
    record.trace_id = "usuario-9876"

    event = json.loads(StructuredJsonFormatter().format(record))

    assert event["event"] == "log_event"
    assert "trace_id" not in event
    assert "9876" not in json.dumps(event)
