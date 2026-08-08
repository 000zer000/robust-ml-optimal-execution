"""Canonical Step 5 event documents and append-only audit-chain utilities.

The C++ structs are authoritative inside the simulation engine.  These Python
helpers define the stable JSON interchange contract used by samples, audit
verification, and future data adapters without introducing a runtime package
dependency.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

EVENT_SCHEMA_MAJOR: Final = 1
EVENT_SCHEMA_MINOR: Final = 0
ZERO_SHA256: Final = "0" * 64
EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "book_snapshot",
        "depth_update",
        "trade",
        "decision",
        "order_submit",
        "order_acknowledged",
        "order_rejected",
        "cancel_request",
        "cancel_acknowledged",
        "cancel_rejected",
        "replace_request",
        "replace_acknowledged",
        "replace_rejected",
        "fill",
        "fee",
        "terminal_completion",
        "timer",
    }
)


class EventModelError(ValueError):
    """Raised when an event or audit record violates the frozen Step 5 contract."""


@dataclass(frozen=True, slots=True)
class AuditVerification:
    records: int
    run_id: str | None
    final_sha256: str


def canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    """Return the exact UTF-8 representation covered by the audit hash."""

    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EventModelError(f"{field} must be an object")
    return value


def _require_nonempty_string(document: Mapping[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value:
        raise EventModelError(f"{field} must be a non-empty string")
    return value


def _require_integer(document: Mapping[str, Any], field: str, *, minimum: int | None = None) -> int:
    value = document.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventModelError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise EventModelError(f"{field} must be >= {minimum}")
    return value


def _validate_schema_version(value: object) -> None:
    version = _require_mapping(value, "schema_version")
    major = _require_integer(version, "major", minimum=1)
    _require_integer(version, "minor", minimum=0)
    if major != EVENT_SCHEMA_MAJOR:
        raise EventModelError(f"unsupported schema major {major}; expected {EVENT_SCHEMA_MAJOR}")


def _validate_timestamp(value: object, field: str) -> tuple[str, int]:
    timestamp = _require_mapping(value, field)
    domain = _require_nonempty_string(timestamp, "domain")
    if domain not in {"unix_utc", "simulation"}:
        raise EventModelError(f"{field}.domain is unsupported")
    return domain, _require_integer(timestamp, "ns")


def _validate_optional_timestamp(document: Mapping[str, Any], field: str) -> tuple[str, int] | None:
    value = document.get(field)
    if value is None:
        return None
    return _validate_timestamp(value, field)


def _validate_ordering(value: object) -> None:
    ordering = _require_mapping(value, "ordering")
    has_source = ordering.get("has_source_sequence")
    if not isinstance(has_source, bool):
        raise EventModelError("ordering.has_source_sequence must be boolean")
    source = _require_integer(ordering, "source_sequence", minimum=0)
    _require_integer(ordering, "source_subsequence", minimum=0)
    _require_integer(ordering, "ingest_sequence", minimum=1)
    _require_integer(ordering, "canonical_sequence", minimum=1)
    if not has_source and source != 0:
        raise EventModelError(
            "ordering.source_sequence must be zero when has_source_sequence is false"
        )


def _validate_action_times(payload: Mapping[str, Any]) -> None:
    decision = _validate_timestamp(payload.get("decision_time"), "decision_time")
    send = _validate_timestamp(payload.get("outbound_send_time"), "outbound_send_time")
    exchange = _validate_timestamp(payload.get("exchange_receive_time"), "exchange_receive_time")
    if (
        decision[0] != send[0]
        or send[0] != exchange[0]
        or not decision[1] <= send[1] <= exchange[1]
    ):
        raise EventModelError("action timestamps must share a clock and be non-decreasing")


def _positive_int(payload: Mapping[str, Any], field: str) -> int:
    return _require_integer(payload, field, minimum=1)


def _nonnegative_int(payload: Mapping[str, Any], field: str) -> int:
    return _require_integer(payload, field, minimum=0)


def _validate_payload(kind: str, value: object) -> None:
    payload = _require_mapping(value, "payload")
    if kind == "book_snapshot":
        for side in ("bids", "asks"):
            levels = payload.get(side)
            if not isinstance(levels, list):
                raise EventModelError(f"payload.{side} must be an array")
            previous: int | None = None
            for level_object in levels:
                level = _require_mapping(level_object, f"payload.{side} level")
                price = _positive_int(level, "price_ticks")
                _positive_int(level, "quantity_lots")
                if previous is not None:
                    ordered = price < previous if side == "bids" else price > previous
                    if not ordered:
                        raise EventModelError(f"payload.{side} is not strictly ordered")
                previous = price
        bids = payload["bids"]
        asks = payload["asks"]
        if bids and asks and bids[0]["price_ticks"] >= asks[0]["price_ticks"]:
            raise EventModelError("book snapshot is crossed or locked")
    elif kind == "depth_update":
        if payload.get("side") not in {"buy", "sell"}:
            raise EventModelError("payload.side must be buy or sell")
        _positive_int(payload, "price_ticks")
        action = payload.get("action")
        quantity = _nonnegative_int(payload, "quantity_after_lots")
        if action == "set" and quantity == 0:
            raise EventModelError("set update requires positive quantity")
        if action == "delete" and quantity != 0:
            raise EventModelError("delete update requires zero quantity")
        if action not in {"set", "delete"}:
            raise EventModelError("payload.action is unsupported")
    elif kind == "trade":
        _positive_int(payload, "trade_id")
        _positive_int(payload, "price_ticks")
        _positive_int(payload, "quantity_lots")
    elif kind == "decision":
        _positive_int(payload, "decision_id")
        _require_nonempty_string(payload, "strategy_id")
        _require_nonempty_string(payload, "action_name")
        cutoff = _validate_timestamp(payload.get("observation_cutoff"), "observation_cutoff")
        start = _validate_timestamp(payload.get("decision_start"), "decision_start")
        end = _validate_timestamp(payload.get("decision_end"), "decision_end")
        if cutoff[0] != start[0] or start[0] != end[0] or not cutoff[1] <= start[1] <= end[1]:
            raise EventModelError("decision timestamps must share a clock and be non-decreasing")
        _nonnegative_int(payload, "remaining_inventory_lots")
    elif kind == "order_submit":
        for field in ("parent_order_id", "client_order_id", "decision_id", "quantity_lots"):
            _positive_int(payload, field)
        if payload.get("side") not in {"buy", "sell"}:
            raise EventModelError("payload.side must be buy or sell")
        if payload.get("time_in_force") not in {"gtc", "ioc", "fok"}:
            raise EventModelError("payload.time_in_force is unsupported")
        if not isinstance(payload.get("post_only"), bool):
            raise EventModelError("payload.post_only must be boolean")
        order_type = payload.get("order_type")
        limit_price = payload.get("limit_price_ticks")
        if order_type == "limit":
            if (
                isinstance(limit_price, bool)
                or not isinstance(limit_price, int)
                or limit_price <= 0
            ):
                raise EventModelError("limit order requires positive limit_price_ticks")
        elif order_type == "market":
            if limit_price is not None:
                raise EventModelError("market order must not include limit_price_ticks")
            if payload.get("post_only") is True:
                raise EventModelError("market order cannot be post-only")
        else:
            raise EventModelError("payload.order_type is unsupported")
        _validate_action_times(payload)
    elif kind == "order_acknowledged":
        _positive_int(payload, "client_order_id")
        _positive_int(payload, "exchange_order_id")
        accepted = _positive_int(payload, "accepted_quantity_lots")
        cumulative = _nonnegative_int(payload, "cumulative_filled_lots")
        leaves = _nonnegative_int(payload, "leaves_quantity_lots")
        if cumulative + leaves != accepted:
            raise EventModelError("acknowledgement quantities do not conserve accepted quantity")
        if payload.get("state") not in {"live", "partially_filled", "filled"}:
            raise EventModelError("acknowledgement state is invalid")
    elif kind == "order_rejected":
        _positive_int(payload, "client_order_id")
    elif kind == "cancel_request":
        _positive_int(payload, "client_order_id")
        _positive_int(payload, "exchange_order_id")
        _positive_int(payload, "decision_id")
        _validate_action_times(payload)
    elif kind == "cancel_acknowledged":
        _positive_int(payload, "client_order_id")
        _positive_int(payload, "exchange_order_id")
        _nonnegative_int(payload, "cumulative_filled_lots")
        _nonnegative_int(payload, "cancelled_quantity_lots")
        if _nonnegative_int(payload, "leaves_quantity_lots") != 0:
            raise EventModelError("cancel acknowledgement must have zero leaves quantity")
        if payload.get("state") != "cancelled":
            raise EventModelError("cancel acknowledgement state must be cancelled")
    elif kind == "cancel_rejected":
        _positive_int(payload, "client_order_id")
        _positive_int(payload, "exchange_order_id")
        if payload.get("resulting_state") in {
            "cancelled",
            "filled",
            "rejected",
            "expired",
            "replaced",
        }:
            raise EventModelError("cancel rejection resulting_state must be non-terminal")
    elif kind == "replace_request":
        for field in (
            "client_order_id",
            "exchange_order_id",
            "replacement_client_order_id",
            "decision_id",
            "new_quantity_lots",
        ):
            _positive_int(payload, field)
        new_price = payload.get("new_limit_price_ticks")
        if new_price is not None and (
            isinstance(new_price, bool) or not isinstance(new_price, int) or new_price <= 0
        ):
            raise EventModelError("new_limit_price_ticks must be null or a positive integer")
        _validate_action_times(payload)
    elif kind == "replace_acknowledged":
        for field in (
            "original_client_order_id",
            "original_exchange_order_id",
            "replacement_client_order_id",
            "replacement_exchange_order_id",
            "accepted_quantity_lots",
        ):
            _positive_int(payload, field)
        if _nonnegative_int(payload, "leaves_quantity_lots") != payload["accepted_quantity_lots"]:
            raise EventModelError("replacement leaves must equal accepted quantity")
    elif kind == "replace_rejected":
        for field in ("client_order_id", "exchange_order_id", "replacement_client_order_id"):
            _positive_int(payload, field)
        if payload.get("resulting_state") in {
            "cancelled",
            "filled",
            "rejected",
            "expired",
            "replaced",
        }:
            raise EventModelError("replace rejection resulting_state must be non-terminal")
    elif kind == "fill":
        for field in (
            "execution_id",
            "client_order_id",
            "exchange_order_id",
            "price_ticks",
            "quantity_lots",
            "cumulative_filled_lots",
        ):
            _positive_int(payload, field)
        _nonnegative_int(payload, "leaves_quantity_lots")
        if payload["quantity_lots"] > payload["cumulative_filled_lots"]:
            raise EventModelError("incremental fill exceeds cumulative fill")
        if payload.get("side") not in {"buy", "sell"}:
            raise EventModelError("fill side must be buy or sell")
        if payload.get("liquidity_role") not in {"unknown", "maker", "taker"}:
            raise EventModelError("fill liquidity_role is unsupported")
    elif kind == "fee":
        _positive_int(payload, "execution_id")
        _require_nonempty_string(payload, "fee_schedule_id")
        _require_integer(payload, "amount_quote_atoms")
        if payload.get("liquidity_role") not in {"unknown", "maker", "taker"}:
            raise EventModelError("fee liquidity_role is unsupported")
    elif kind == "terminal_completion":
        _positive_int(payload, "parent_order_id")
        _positive_int(payload, "quantity_lots")
        _positive_int(payload, "price_ticks")
        _require_integer(payload, "explicit_fee_quote_atoms")
        _require_nonempty_string(payload, "rule_id")
        if payload.get("side") not in {"buy", "sell"}:
            raise EventModelError("terminal side must be buy or sell")
    elif kind == "timer":
        _require_nonempty_string(payload, "timer_name")
        _nonnegative_int(payload, "occurrence")


def validate_event_document(document: Mapping[str, Any]) -> None:
    """Validate the stable, venue-neutral event envelope and core invariants."""

    document = _require_mapping(document, "event")
    _validate_schema_version(document.get("schema_version"))
    _positive_int(document, "event_id")
    for field in ("run_id", "venue", "instrument", "source_channel"):
        _require_nonempty_string(document, field)
    if document.get("origin") not in {
        "historical_feed",
        "synthetic_exchange",
        "strategy",
        "system",
    }:
        raise EventModelError("origin is unsupported")
    exchange = _validate_timestamp(document.get("event_time"), "event_time")
    receive = _validate_optional_timestamp(document, "receive_time")
    available = _validate_optional_timestamp(document, "available_time")
    if receive is not None:
        if receive[0] != exchange[0]:
            raise EventModelError("event_time and receive_time use different clocks")
        if receive[1] < exchange[1] and document.get("origin") != "historical_feed":
            raise EventModelError("receive_time precedes event_time for a non-historical event")
    if available is not None:
        if receive is None:
            raise EventModelError("available_time requires receive_time")
        if available[0] != receive[0] or available[1] < receive[1]:
            raise EventModelError("available_time must share the clock and follow receive_time")
    _validate_ordering(document.get("ordering"))
    kind = _require_nonempty_string(document, "kind")
    if kind not in EVENT_KINDS:
        raise EventModelError(f"unsupported event kind: {kind}")
    _validate_payload(kind, document.get("payload"))


def _record_hash_material(record: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(record)
    material.pop("record_sha256", None)
    return material


def _sha256_hex(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


class AuditLogWriter:
    """Create one new immutable hash-chained JSONL audit log.

    Existing non-empty paths are rejected.  This deliberately avoids an API
    that can rewrite or truncate prior records.
    """

    def __init__(self, path: Path, run_id: str) -> None:
        if not run_id:
            raise EventModelError("run_id must be non-empty")
        if path.exists() and path.stat().st_size != 0:
            raise FileExistsError(f"refusing to modify existing audit log: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._run_id = run_id
        self._next_index = 0
        self._previous_sha256 = ZERO_SHA256

    def append(self, event: Mapping[str, Any]) -> str:
        validate_event_document(event)
        if event["run_id"] != self._run_id:
            raise EventModelError("event run_id does not match audit log run_id")
        record: dict[str, Any] = {
            "schema_version": {"major": EVENT_SCHEMA_MAJOR, "minor": EVENT_SCHEMA_MINOR},
            "run_id": self._run_id,
            "append_index": self._next_index,
            "previous_record_sha256": self._previous_sha256,
            "event": dict(event),
        }
        record_hash = _sha256_hex(record)
        record["record_sha256"] = record_hash
        with self._path.open("ab") as handle:
            handle.write(canonical_json_bytes(record))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._next_index += 1
        self._previous_sha256 = record_hash
        return record_hash


def verify_audit_log(path: Path) -> AuditVerification:
    """Verify syntax, event validity, append order, run identity, and hash chain."""

    previous_hash = ZERO_SHA256
    expected_index = 0
    run_id: str | None = None
    with path.open("rb") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                raise EventModelError("audit log contains an empty record")
            try:
                record_object = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise EventModelError("audit log contains invalid JSON") from error
            record = _require_mapping(record_object, "audit record")
            _validate_schema_version(record.get("schema_version"))
            current_run_id = _require_nonempty_string(record, "run_id")
            if run_id is None:
                run_id = current_run_id
            elif current_run_id != run_id:
                raise EventModelError("audit log contains multiple run_id values")
            if _require_integer(record, "append_index", minimum=0) != expected_index:
                raise EventModelError("audit append_index is not contiguous")
            if record.get("previous_record_sha256") != previous_hash:
                raise EventModelError("audit previous hash does not match chain")
            record_hash = _require_nonempty_string(record, "record_sha256")
            if len(record_hash) != 64 or any(
                character not in "0123456789abcdef" for character in record_hash
            ):
                raise EventModelError("record_sha256 is not lowercase SHA-256 hex")
            expected_hash = _sha256_hex(_record_hash_material(record))
            if record_hash != expected_hash:
                raise EventModelError("audit record hash mismatch")
            event = _require_mapping(record.get("event"), "event")
            validate_event_document(event)
            if event.get("run_id") != current_run_id:
                raise EventModelError("audit record and event run_id differ")
            previous_hash = record_hash
            expected_index += 1
    return AuditVerification(expected_index, run_id, previous_hash)


def write_audit_log(
    path: Path, run_id: str, events: Iterable[Mapping[str, Any]]
) -> AuditVerification:
    writer = AuditLogWriter(path, run_id)
    for event in events:
        writer.append(event)
    return verify_audit_log(path)
