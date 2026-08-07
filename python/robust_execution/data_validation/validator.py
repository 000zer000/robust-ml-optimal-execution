"""Independent Step 13 validation, admission, and quarantine engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from robust_execution import __version__
from robust_execution.data_capture.sequence import DepthSynchronizer, SequenceError, parse_depth_update
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.data_capture.verify import CaptureVerificationError, verify_capture_manifest
from robust_execution.data_validation.config import DataValidationConfig
from robust_execution.data_validation.models import DayCounters, DayDecision, ValidationIssue


class DataValidationError(RuntimeError):
    """Raised when validation cannot produce trustworthy evidence."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utc_day(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).date().isoformat()


def _day_bounds(day_text: str) -> tuple[int, int]:
    parsed = date.fromisoformat(day_text)
    start = datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1_000_000_000), int(end.timestamp() * 1_000_000_000)


def _positive_decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return parsed


def _load_snapshot(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"cannot read snapshot {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DataValidationError(f"snapshot is not an object: {path}")
    return value


def _load_records(manifest_path: Path, issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    records: list[dict[str, Any]] = []
    for artifact in manifest.get("artifacts", []):
        relative = artifact.get("relative_path")
        if not isinstance(relative, str) or "segment-" not in Path(relative).name:
            continue
        path = root / relative
        try:
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                for line_number, line in enumerate(handle, 1):
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        issues.append(
                            ValidationIssue(
                                code="record_json_invalid",
                                severity="critical",
                                scope="record",
                                detail=f"invalid record JSON at line {line_number}: {exc}",
                                quarantine=True,
                                relative_path=relative,
                            )
                        )
                        continue
                    if isinstance(record, dict):
                        record["_relative_path"] = relative
                        records.append(record)
                    else:
                        issues.append(
                            ValidationIssue(
                                code="record_not_object",
                                severity="critical",
                                scope="record",
                                detail=f"record at line {line_number} is not an object",
                                quarantine=True,
                                relative_path=relative,
                            )
                        )
        except OSError as exc:
            issues.append(
                ValidationIssue(
                    code="segment_unreadable",
                    severity="critical",
                    scope="artifact",
                    detail=str(exc),
                    quarantine=True,
                    relative_path=relative,
                )
            )
    return records


def _issue_for_record(
    record: dict[str, Any], code: str, detail: str, *, severity: str = "critical", quarantine: bool = True
) -> ValidationIssue:
    received = record.get("received_utc_ns")
    return ValidationIssue(
        code=code,
        severity=severity,
        scope="record",
        detail=detail,
        quarantine=quarantine,
        day=_utc_day(received) if isinstance(received, int) and received >= 0 else None,
        symbol=record.get("symbol") if isinstance(record.get("symbol"), str) else None,
        connection_id=(
            record.get("connection_id") if isinstance(record.get("connection_id"), str) else None
        ),
        message_index=(record.get("message_index") if isinstance(record.get("message_index"), int) else None),
        received_utc_ns=received if isinstance(received, int) else None,
        relative_path=record.get("_relative_path"),
    )


def _validate_record_envelope(
    record: dict[str, Any], manifest: dict[str, Any], issues: list[ValidationIssue]
) -> tuple[dict[str, Any] | None, str | None]:
    required_types: dict[str, type] = {
        "schema_version": int,
        "run_id": str,
        "connection_id": str,
        "message_index": int,
        "received_utc_ns": int,
        "received_monotonic_ns": int,
        "stream": str,
        "raw_payload_sha256": str,
        "raw_payload_utf8": str,
    }
    for field, expected in required_types.items():
        value = record.get(field)
        if not isinstance(value, expected) or isinstance(value, bool):
            issues.append(_issue_for_record(record, "record_schema_invalid", f"{field} has invalid type"))
            return None, None
    if record["schema_version"] != 1 or record["run_id"] != manifest.get("run_id"):
        issues.append(_issue_for_record(record, "record_provenance_mismatch", "schema_version or run_id mismatch"))
        return None, None
    if record["message_index"] < 0 or record["received_utc_ns"] < 0 or record["received_monotonic_ns"] < 0:
        issues.append(_issue_for_record(record, "record_negative_index_or_timestamp", "index and timestamps must be non-negative"))
        return None, None
    raw = record["raw_payload_utf8"].encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != record["raw_payload_sha256"]:
        issues.append(_issue_for_record(record, "raw_payload_hash_mismatch", "embedded raw payload hash mismatch"))
        return None, None
    try:
        wrapper = json.loads(record["raw_payload_utf8"])
    except json.JSONDecodeError as exc:
        issues.append(_issue_for_record(record, "raw_payload_json_invalid", str(exc)))
        return None, None
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("stream"), str) or not isinstance(wrapper.get("data"), dict):
        issues.append(_issue_for_record(record, "combined_stream_wrapper_invalid", "expected Binance combined stream wrapper"))
        return None, None
    data = wrapper["data"]
    if wrapper["stream"] != record["stream"]:
        issues.append(_issue_for_record(record, "stream_mismatch", "stored stream differs from raw wrapper"))
    symbol = data.get("s")
    event_type = data.get("e")
    if symbol != record.get("symbol") or event_type != record.get("event_type"):
        issues.append(_issue_for_record(record, "payload_metadata_mismatch", "symbol or event type differs from raw payload"))
    return data, event_type if isinstance(event_type, str) else None


def _validate_trade(record: dict[str, Any], payload: dict[str, Any], issues: list[ValidationIssue]) -> tuple[str, int] | None:
    try:
        if payload.get("e") != "trade":
            raise ValueError("event type is not trade")
        symbol = payload.get("s")
        trade_id = payload.get("t")
        event_time = payload.get("E")
        trade_time = payload.get("T")
        if not isinstance(symbol, str) or not isinstance(trade_id, int) or isinstance(trade_id, bool) or trade_id < 0:
            raise ValueError("invalid symbol or trade id")
        for name, value in (("E", event_time), ("T", trade_time)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _positive_decimal(payload.get("p"), "trade price")
        _positive_decimal(payload.get("q"), "trade quantity")
        if not isinstance(payload.get("m"), bool):
            raise ValueError("trade maker flag must be boolean")
    except ValueError as exc:
        issues.append(_issue_for_record(record, "trade_invalid", str(exc)))
        return None
    received = record["received_utc_ns"]
    event_ns = int(event_time) * 1000
    return symbol, event_ns


def _validate_time_delta(record: dict[str, Any], event_ns: int, maximum: int, issues: list[ValidationIssue]) -> None:
    delta = record["received_utc_ns"] - event_ns
    if abs(delta) > maximum:
        issues.append(
            _issue_for_record(
                record,
                "event_receive_delta_excessive",
                f"absolute exchange/local timestamp delta {abs(delta)} exceeds {maximum}",
            )
        )


def validate_capture_data(
    manifest_path: Path,
    config: DataValidationConfig,
    output_root: Path,
    *,
    validation_id: str | None = None,
) -> Path:
    """Validate one immutable Step 12 capture and write immutable Step 13 evidence."""
    try:
        source_verification = verify_capture_manifest(manifest_path)
    except CaptureVerificationError as exc:
        raise DataValidationError(f"source capture verification failed: {exc}") from exc
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("venue_id") != config.venue_id or tuple(manifest.get("symbols", [])) != config.symbols:
        raise DataValidationError("capture venue or symbols differ from validation contract")
    if manifest.get("data_origin") not in config.allowed_data_origins:
        raise DataValidationError("capture data origin is not allowed")
    identifier = validation_id or f"step13-{manifest['run_id']}"
    target = output_root / identifier
    if target.exists():
        raise DataValidationError(f"validation output already exists: {target}")
    target.mkdir(parents=True)

    issues: list[ValidationIssue] = []
    records = _load_records(manifest_path, issues)
    day_counters: dict[str, DayCounters] = defaultdict(DayCounters)
    connection_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    parsed_depth: dict[tuple[str, str], list[tuple[dict[str, Any], Any]]] = defaultdict(list)
    trade_ids: dict[str, set[int]] = defaultdict(set)

    for record in records:
        received = record.get("received_utc_ns")
        if isinstance(received, int) and received >= 0:
            day = _utc_day(received)
            counters = day_counters[day]
            counters.total_messages += 1
            counters.first_received_utc_ns = (
                received if counters.first_received_utc_ns is None else min(counters.first_received_utc_ns, received)
            )
            counters.last_received_utc_ns = (
                received if counters.last_received_utc_ns is None else max(counters.last_received_utc_ns, received)
            )
            path_day = Path(str(record.get("_relative_path", ""))).parent.name
            if path_day != day:
                issues.append(_issue_for_record(record, "segment_day_mismatch", f"segment day {path_day} differs from receive day {day}"))
        connection = record.get("connection_id")
        if isinstance(connection, str):
            connection_records[connection].append(record)
        payload, event_type = _validate_record_envelope(record, manifest, issues)
        if payload is None:
            continue
        symbol = payload.get("s")
        if symbol not in config.symbols:
            issues.append(_issue_for_record(record, "unexpected_symbol", f"unexpected symbol {symbol!r}"))
            continue
        day = _utc_day(record["received_utc_ns"])
        if event_type == "depthUpdate":
            day_counters[day].depth_messages[symbol] = day_counters[day].depth_messages.get(symbol, 0) + 1
            try:
                update = parse_depth_update(payload)
                parsed_depth[(record["connection_id"], symbol)].append((record, update))
                _validate_time_delta(record, update.event_time * 1000, config.admission.maximum_event_receive_delta_ns, issues)
            except SequenceError as exc:
                issues.append(_issue_for_record(record, "depth_update_invalid", str(exc)))
        elif event_type == "trade":
            day_counters[day].trade_messages[symbol] = day_counters[day].trade_messages.get(symbol, 0) + 1
            result = _validate_trade(record, payload, issues)
            if result is not None:
                parsed_symbol, event_ns = result
                _validate_time_delta(record, event_ns, config.admission.maximum_event_receive_delta_ns, issues)
                trade_id = int(payload["t"])
                if trade_id in trade_ids[parsed_symbol]:
                    day_counters[day].duplicate_trade_messages += 1
                    issues.append(_issue_for_record(record, "duplicate_trade_id", f"duplicate trade id {trade_id}", severity="warning", quarantine=False))
                trade_ids[parsed_symbol].add(trade_id)
        else:
            issues.append(_issue_for_record(record, "unexpected_event_type", f"unsupported event type {event_type!r}"))

    connection_manifest = {item.get("connection_id"): item for item in manifest.get("connections", []) if isinstance(item, dict)}
    for connection_id, items in connection_records.items():
        ordered = sorted(items, key=lambda item: item.get("message_index", -1))
        indexes = [item.get("message_index") for item in ordered]
        if indexes != list(range(len(ordered))):
            issues.append(ValidationIssue(code="message_index_discontinuity", severity="critical", scope="connection", detail=f"{connection_id} indexes are not contiguous from zero", quarantine=True, connection_id=connection_id))
        utc_values = [item.get("received_utc_ns") for item in ordered if isinstance(item.get("received_utc_ns"), int)]
        monotonic_values = [item.get("received_monotonic_ns") for item in ordered if isinstance(item.get("received_monotonic_ns"), int)]
        if utc_values != sorted(utc_values):
            issues.append(ValidationIssue(code="receive_utc_reversal", severity="critical", scope="connection", detail=f"{connection_id} UTC receive timestamps reverse", quarantine=True, connection_id=connection_id))
        if monotonic_values != sorted(monotonic_values):
            issues.append(ValidationIssue(code="receive_monotonic_reversal", severity="critical", scope="connection", detail=f"{connection_id} monotonic timestamps reverse", quarantine=True, connection_id=connection_id))
        expected_count = connection_manifest.get(connection_id, {}).get("messages")
        if expected_count != len(items):
            issues.append(ValidationIssue(code="connection_message_count_mismatch", severity="critical", scope="connection", detail=f"{connection_id} manifest count {expected_count} differs from {len(items)}", quarantine=True, connection_id=connection_id))

    snapshot_root = manifest_path.parent / "snapshots"
    for connection_id in connection_records:
        for symbol in config.symbols:
            candidates = sorted((snapshot_root / symbol).glob(f"{connection_id}-*.json.gz"))
            updates = parsed_depth.get((connection_id, symbol), [])
            if not candidates:
                issues.append(ValidationIssue(code="snapshot_missing", severity="critical", scope="connection_symbol", detail=f"no snapshot for {connection_id}/{symbol}", quarantine=True, symbol=symbol, connection_id=connection_id))
                continue
            if len(candidates) != 1:
                issues.append(ValidationIssue(code="snapshot_ambiguous", severity="critical", scope="connection_symbol", detail=f"expected one snapshot for {connection_id}/{symbol}, found {len(candidates)}", quarantine=True, symbol=symbol, connection_id=connection_id))
                continue
            sync = DepthSynchronizer(symbol)
            for record, update in updates:
                sync.ingest(update)
            try:
                if not sync.install_snapshot(_load_snapshot(candidates[0])):
                    issues.append(ValidationIssue(code="snapshot_delta_no_overlap", severity="critical", scope="connection_symbol", detail=f"snapshot does not overlap buffered updates for {connection_id}/{symbol}", quarantine=True, symbol=symbol, connection_id=connection_id, relative_path=str(candidates[0].relative_to(manifest_path.parent))))
                if sync.state.value != "synchronized":
                    issues.append(ValidationIssue(code="depth_not_synchronized", severity="critical", scope="connection_symbol", detail=f"depth did not finish synchronized for {connection_id}/{symbol}", quarantine=True, symbol=symbol, connection_id=connection_id))
            except SequenceError as exc:
                issues.append(ValidationIssue(code="book_reconstruction_failed", severity="critical", scope="connection_symbol", detail=str(exc), quarantine=True, symbol=symbol, connection_id=connection_id, relative_path=str(candidates[0].relative_to(manifest_path.parent))))

    decisions: list[DayDecision] = []
    for day, counters in sorted(day_counters.items()):
        day_issues = [item for item in issues if item.day in {None, day} and item.severity == "critical"]
        day_warnings = [item for item in issues if item.day == day and item.severity == "warning"]
        reasons: list[str] = []
        start_ns, end_ns = _day_bounds(day)
        if counters.first_received_utc_ns is None or counters.last_received_utc_ns is None:
            reasons.append("no_messages")
        elif config.admission.require_whole_utc_day and (
            counters.first_received_utc_ns > start_ns + config.admission.boundary_tolerance_ns
            or counters.last_received_utc_ns < end_ns - config.admission.boundary_tolerance_ns
        ):
            reasons.append("incomplete_utc_day_coverage")
        for symbol in config.symbols:
            if counters.depth_messages.get(symbol, 0) < config.admission.minimum_depth_messages_per_symbol:
                reasons.append(f"insufficient_depth_messages:{symbol}")
            if counters.trade_messages.get(symbol, 0) < config.admission.minimum_trade_messages_per_symbol:
                reasons.append(f"insufficient_trade_messages:{symbol}")
        if day_issues:
            reasons.append("critical_validation_issue")
        structural_status = "valid" if not reasons else "invalid"
        admission_reasons = list(reasons)
        if config.admission.require_live_origin and manifest.get("data_origin") != "live_binance":
            admission_reasons.append("non_live_fixture_origin")
        if config.admission.require_capture_complete and manifest.get("status") != "complete":
            admission_reasons.append("capture_not_complete")
        if config.admission.require_72h_pilot and manifest.get("pilot_72h_complete") is not True:
            admission_reasons.append("live_72h_pilot_not_complete")
        if structural_status == "invalid":
            admission_status = "quarantined"
        elif admission_reasons:
            admission_status = "fixture_valid_not_admissible" if manifest.get("data_origin") == "synthetic_transport_fixture" else "not_admissible"
        else:
            admission_status = "admitted"
        decisions.append(DayDecision(day=day, structural_status=structural_status, admission_status=admission_status, reasons=tuple(dict.fromkeys(admission_reasons)), total_messages=counters.total_messages, depth_messages=dict(sorted(counters.depth_messages.items())), trade_messages=dict(sorted(counters.trade_messages.items())), first_received_utc_ns=counters.first_received_utc_ns, last_received_utc_ns=counters.last_received_utc_ns, critical_issue_count=len(day_issues), warning_count=len(day_warnings)))

    if not decisions:
        issues.append(ValidationIssue(code="capture_contains_no_days", severity="critical", scope="capture", detail="capture contains no raw records", quarantine=True))

    config_bytes = _canonical_bytes(config.to_dict()) + b"\n"
    report = {
        "schema_version": 1,
        "step": 13,
        "validation_id": identifier,
        "source_run_id": manifest.get("run_id"),
        "source_manifest_sha256": source_verification["manifest_sha256"],
        "venue_id": config.venue_id,
        "symbols": list(config.symbols),
        "data_origin": manifest.get("data_origin"),
        "software_version": __version__,
        "validation_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "research_specification_changed": False,
        "missing_events_repaired": False,
        "source_capture_verified": True,
        "total_raw_records": len(records),
        "issue_counts": {
            "critical": sum(item.severity == "critical" for item in issues),
            "warning": sum(item.severity == "warning" for item in issues),
        },
        "days": [item.to_dict() for item in decisions],
        "summary": {
            "admitted_days": sum(item.admission_status == "admitted" for item in decisions),
            "quarantined_days": sum(item.admission_status == "quarantined" for item in decisions),
            "structurally_valid_days": sum(item.structural_status == "valid" for item in decisions),
            "non_admissible_valid_days": sum(item.structural_status == "valid" and item.admission_status != "admitted" for item in decisions),
        },
    }
    quarantine = {
        "schema_version": 1,
        "step": 13,
        "validation_id": identifier,
        "source_run_id": manifest.get("run_id"),
        "policy": "preserve_raw_never_repair_primary_history",
        "issues": [item.to_dict() for item in issues],
        "quarantined_days": [item.day for item in decisions if item.admission_status == "quarantined"],
    }
    write_immutable_json(target / "validation-config.json", config.to_dict())
    write_immutable_json(target / "quarantine-manifest.json", quarantine)
    write_immutable_json(target / "validation-report.json", report)
    report_hash = hashlib.sha256((target / "validation-report.json").read_bytes()).hexdigest()
    quarantine_hash = hashlib.sha256((target / "quarantine-manifest.json").read_bytes()).hexdigest()
    write_immutable_json(target / "validation-report.sha256.json", {"sha256": report_hash})
    write_immutable_json(target / "quarantine-manifest.sha256.json", {"sha256": quarantine_hash})
    return target / "validation-report.json"
