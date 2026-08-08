"""Canonical Step 12 capture records and manifest helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RawMessageRecord:
    schema_version: int
    run_id: str
    connection_id: str
    message_index: int
    received_utc_ns: int
    received_monotonic_ns: int
    stream: str
    symbol: str | None
    event_type: str | None
    raw_payload_sha256: str
    raw_payload_utf8: str

    def to_bytes(self) -> bytes:
        raw = self.raw_payload_utf8.encode("utf-8")
        if sha256_hex(raw) != self.raw_payload_sha256:
            raise ValueError("raw payload hash mismatch")
        return canonical_json_bytes(asdict(self))


@dataclass(frozen=True)
class ArtifactRecord:
    relative_path: str
    content_type: str
    compression: str
    uncompressed_bytes: int
    compressed_bytes: int
    record_count: int
    sha256: str


@dataclass
class ConnectionRecord:
    connection_id: str
    endpoint: str
    started_utc_ns: int
    ended_utc_ns: int | None = None
    close_code: int | None = None
    close_reason: str | None = None
    outcome: str = "open"
    messages: int = 0
    selected_remote: str | None = None


@dataclass
class SymbolDiagnostics:
    symbol: str
    snapshots: int = 0
    buffered_events: int = 0
    applied_events: int = 0
    ignored_events: int = 0
    duplicate_events: int = 0
    gaps: int = 0
    malformed_events: int = 0
    crossed_books: int = 0
    resynchronizations: int = 0
    first_update_id: int | None = None
    last_update_id: int | None = None
    synchronized: bool = False
    synchronized_intervals: list[dict[str, int]] = field(default_factory=list)


@dataclass
class CaptureManifest:
    schema_version: int
    step: int
    run_id: str
    venue_id: str
    data_origin: str
    symbols: list[str]
    status: str
    started_utc_ns: int
    ended_utc_ns: int | None
    planned_duration_seconds: int
    actual_duration_seconds: float
    pilot_72h_complete: bool
    websocket_url: str
    rest_base: str
    compression: str
    exact_raw_payload_preserved: bool
    research_specification_changed: bool
    paid_data_used: bool
    software_version: str
    runtime: dict[str, str]
    capture_config_sha256: str
    total_messages: int
    total_raw_payload_bytes: int
    total_uncompressed_bytes: int
    total_compressed_bytes: int
    connections: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    symbol_diagnostics: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    publication: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
