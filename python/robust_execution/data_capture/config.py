"""Validated configuration for Binance Spot raw capture."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class CaptureConfigurationError(ValueError):
    """Raised when a capture configuration violates the Step 12 contract."""


@dataclass(frozen=True)
class StorageConfig:
    output_root: Path
    compression: str
    segment_max_messages: int
    segment_max_uncompressed_bytes: int
    fsync_each_record: bool
    fsync_interval_messages: int


@dataclass(frozen=True)
class PilotConfig:
    required_duration_seconds: int
    rotate_before_seconds: int
    reconnect_backoff_seconds: float
    receive_timeout_seconds: float
    max_reconnects: int


@dataclass(frozen=True)
class CaptureConfig:
    schema_version: int
    venue_id: str
    symbols: tuple[str, ...]
    websocket_base: str
    rest_base: str
    depth_stream_suffix: str
    trade_stream_suffix: str
    timestamp_unit: str
    snapshot_limit: int
    storage: StorageConfig
    pilot: PilotConfig
    research_specification_changed: bool
    paid_data_required: bool

    def combined_stream_url(self) -> str:
        streams: list[str] = []
        for symbol in self.symbols:
            lower = symbol.lower()
            streams.extend(
                [f"{lower}{self.depth_stream_suffix}", f"{lower}{self.trade_stream_suffix}"]
            )
        joined = "/".join(streams)
        return f"{self.websocket_base}/stream?streams={joined}&timeUnit={self.timestamp_unit}"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "venue_id": self.venue_id,
            "symbols": list(self.symbols),
            "websocket_base": self.websocket_base,
            "rest_base": self.rest_base,
            "streams": {
                "depth": self.depth_stream_suffix,
                "trade": self.trade_stream_suffix,
            },
            "timestamp_unit": self.timestamp_unit,
            "snapshot_limit": self.snapshot_limit,
            "storage": {
                "output_root": str(self.storage.output_root),
                "compression": self.storage.compression,
                "segment_max_messages": self.storage.segment_max_messages,
                "segment_max_uncompressed_bytes": self.storage.segment_max_uncompressed_bytes,
                "fsync_each_record": self.storage.fsync_each_record,
                "fsync_interval_messages": self.storage.fsync_interval_messages,
            },
            "pilot": {
                "required_duration_seconds": self.pilot.required_duration_seconds,
                "rotate_before_seconds": self.pilot.rotate_before_seconds,
                "reconnect_backoff_seconds": self.pilot.reconnect_backoff_seconds,
                "receive_timeout_seconds": self.pilot.receive_timeout_seconds,
                "max_reconnects": self.pilot.max_reconnects,
            },
            "research_specification_changed": self.research_specification_changed,
            "paid_data_required": self.paid_data_required,
        }


def _require_int(payload: dict[str, Any], key: str, minimum: int) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CaptureConfigurationError(f"{key} must be an integer >= {minimum}")
    return value


def _require_number(payload: dict[str, Any], key: str, minimum: float) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < minimum:
        raise CaptureConfigurationError(f"{key} must be a number >= {minimum}")
    return float(value)


def _require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise CaptureConfigurationError(f"{key} must be boolean")
    return value


def _require_url(value: object, *, scheme: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CaptureConfigurationError(f"{field} must be a non-empty string")
    parsed = urlparse(value)
    if parsed.scheme != scheme or not parsed.netloc or parsed.query or parsed.fragment:
        raise CaptureConfigurationError(f"{field} must be a clean {scheme} base URL")
    return value.rstrip("/")


def load_capture_config(path: Path) -> CaptureConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureConfigurationError(f"cannot load capture configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaptureConfigurationError("capture configuration root must be an object")

    schema_version = _require_int(raw, "schema_version", 1)
    if schema_version != 1:
        raise CaptureConfigurationError("only capture schema_version 1 is supported")
    if raw.get("venue_id") != "binance_spot":
        raise CaptureConfigurationError("venue_id must remain binance_spot for Step 12")

    symbols_raw = raw.get("symbols")
    if not isinstance(symbols_raw, list) or any(not isinstance(v, str) for v in symbols_raw):
        raise CaptureConfigurationError("symbols must be an array of strings")
    symbols = tuple(symbols_raw)
    if symbols != ("BTCUSDT", "ETHUSDT"):
        raise CaptureConfigurationError("symbols must be exactly BTCUSDT then ETHUSDT")

    streams = raw.get("streams")
    if not isinstance(streams, dict):
        raise CaptureConfigurationError("streams must be an object")
    if streams.get("depth") != "@depth@100ms" or streams.get("trade") != "@trade":
        raise CaptureConfigurationError("Step 12 requires @depth@100ms and @trade streams")

    storage_raw = raw.get("storage")
    pilot_raw = raw.get("pilot")
    if not isinstance(storage_raw, dict) or not isinstance(pilot_raw, dict):
        raise CaptureConfigurationError("storage and pilot must be objects")
    compression = storage_raw.get("compression")
    if compression != "gzip":
        raise CaptureConfigurationError("the executable Step 12 format is gzip")
    output_root = storage_raw.get("output_root")
    if not isinstance(output_root, str) or not output_root:
        raise CaptureConfigurationError("storage.output_root must be a non-empty path")

    timestamp_unit = raw.get("timestamp_unit")
    if timestamp_unit != "MICROSECOND":
        raise CaptureConfigurationError("timestamp_unit must be MICROSECOND")
    snapshot_limit = _require_int(raw, "snapshot_limit", 1)
    if snapshot_limit != 5000:
        raise CaptureConfigurationError("snapshot_limit must be 5000")

    required_duration = _require_int(pilot_raw, "required_duration_seconds", 1)
    if required_duration != 72 * 60 * 60:
        raise CaptureConfigurationError("the pilot requirement must remain exactly 72 hours")
    rotate_before = _require_int(pilot_raw, "rotate_before_seconds", 1)
    if rotate_before >= 24 * 60 * 60:
        raise CaptureConfigurationError("rotation must occur before the 24-hour connection limit")

    config = CaptureConfig(
        schema_version=schema_version,
        venue_id="binance_spot",
        symbols=symbols,
        websocket_base=_require_url(
            raw.get("websocket_base"), scheme="wss", field="websocket_base"
        ),
        rest_base=_require_url(raw.get("rest_base"), scheme="https", field="rest_base"),
        depth_stream_suffix="@depth@100ms",
        trade_stream_suffix="@trade",
        timestamp_unit=timestamp_unit,
        snapshot_limit=snapshot_limit,
        storage=StorageConfig(
            output_root=Path(output_root),
            compression=compression,
            segment_max_messages=_require_int(storage_raw, "segment_max_messages", 1),
            segment_max_uncompressed_bytes=_require_int(
                storage_raw, "segment_max_uncompressed_bytes", 1024
            ),
            fsync_each_record=_require_bool(storage_raw, "fsync_each_record"),
            fsync_interval_messages=_require_int(
                storage_raw, "fsync_interval_messages", 1
            ),
        ),
        pilot=PilotConfig(
            required_duration_seconds=required_duration,
            rotate_before_seconds=rotate_before,
            reconnect_backoff_seconds=_require_number(
                pilot_raw, "reconnect_backoff_seconds", 0.0
            ),
            receive_timeout_seconds=_require_number(
                pilot_raw, "receive_timeout_seconds", 0.1
            ),
            max_reconnects=_require_int(pilot_raw, "max_reconnects", 0),
        ),
        research_specification_changed=_require_bool(raw, "research_specification_changed"),
        paid_data_required=_require_bool(raw, "paid_data_required"),
    )
    if config.research_specification_changed:
        raise CaptureConfigurationError("Step 12 must not change the frozen research specification")
    if config.paid_data_required:
        raise CaptureConfigurationError("self-capture must not require paid data")
    return config
