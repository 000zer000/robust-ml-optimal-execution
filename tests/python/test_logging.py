import json
import logging

from robust_execution.logging import JsonFormatter, configure_logging


def test_json_formatter_has_stable_schema() -> None:
    record = logging.LogRecord(
        name="robust_execution.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.event = "test_event"  # type: ignore[attr-defined]
    record.fields = {"value": 3}  # type: ignore[attr-defined]
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["event"] == "test_event"
    assert payload["fields"] == {"value": 3}


def test_json_formatter_omits_optional_fields() -> None:
    record = logging.LogRecord(
        name="robust_execution.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="plain",
        args=(),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert "event" not in payload
    assert "fields" not in payload


def test_plain_logging_configuration() -> None:
    configure_logging("WARNING", json_output=False)
    logger = logging.getLogger("robust_execution")
    assert logger.level == logging.WARNING
    assert logger.propagate is False
    assert isinstance(logger.handlers[0].formatter, logging.Formatter)
