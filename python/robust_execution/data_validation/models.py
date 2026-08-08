"""Machine-readable Step 13 validation records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    scope: str
    detail: str
    quarantine: bool
    day: str | None = None
    symbol: str | None = None
    connection_id: str | None = None
    message_index: int | None = None
    received_utc_ns: int | None = None
    relative_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DayCounters:
    total_messages: int = 0
    depth_messages: dict[str, int] = field(default_factory=dict)
    trade_messages: dict[str, int] = field(default_factory=dict)
    duplicate_depth_messages: int = 0
    duplicate_trade_messages: int = 0
    first_received_utc_ns: int | None = None
    last_received_utc_ns: int | None = None


@dataclass(frozen=True)
class DayDecision:
    day: str
    structural_status: str
    admission_status: str
    reasons: tuple[str, ...]
    total_messages: int
    depth_messages: dict[str, int]
    trade_messages: dict[str, int]
    first_received_utc_ns: int | None
    last_received_utc_ns: int | None
    critical_issue_count: int
    warning_count: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value
