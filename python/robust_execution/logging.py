"""Structured logging with deterministic field names and stderr output."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp_utc": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if event is not None:
            payload["event"] = event
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload["fields"] = fields
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """Configure the project logger without mutating deterministic artifacts."""
    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))

    project_logger = logging.getLogger("robust_execution")
    project_logger.handlers.clear()
    project_logger.addHandler(handler)
    project_logger.setLevel(level.upper())
    project_logger.propagate = False
