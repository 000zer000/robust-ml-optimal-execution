from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from robust_execution.event_model import (
    AuditLogWriter,
    EventModelError,
    canonical_json_bytes,
    validate_event_document,
    verify_audit_log,
    write_audit_log,
)
from robust_execution.event_sample import sample_events, write_event_model_sample


def test_sample_events_validate() -> None:
    events = sample_events()
    assert len(events) == 9
    for event in events:
        validate_event_document(event)


def test_canonical_json_is_stable_and_rejects_nan() -> None:
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": float("nan")})


def test_event_validation_rejects_invalid_core_fields() -> None:
    event = copy.deepcopy(sample_events()[0])
    event["event_id"] = 0
    with pytest.raises(EventModelError, match="event_id"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["origin"] = "invented"
    with pytest.raises(EventModelError, match="origin"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["available_time"] = {"domain": "simulation", "ns": 1}
    with pytest.raises(EventModelError, match="available_time"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["ordering"]["has_source_sequence"] = False
    with pytest.raises(EventModelError, match="source_sequence"):
        validate_event_document(event)


def test_event_validation_rejects_bad_books_and_orders() -> None:
    event = copy.deepcopy(sample_events()[0])
    event["payload"]["bids"] = [
        {"price_ticks": 99, "quantity_lots": 1, "order_count": None},
        {"price_ticks": 100, "quantity_lots": 1, "order_count": None},
    ]
    with pytest.raises(EventModelError, match="strictly ordered"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["payload"]["bids"][0]["price_ticks"] = 101
    with pytest.raises(EventModelError, match="crossed"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[2])
    event["payload"]["order_type"] = "market"
    with pytest.raises(EventModelError, match="limit_price_ticks"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[3])
    event["payload"]["leaves_quantity_lots"] = 1
    with pytest.raises(EventModelError, match="conserve"):
        validate_event_document(event)


def test_event_validation_rejects_bad_payload_specific_values() -> None:
    event = copy.deepcopy(sample_events()[1])
    event["payload"]["decision_end"]["ns"] = 1
    with pytest.raises(EventModelError, match="decision timestamps"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[4])
    event["payload"]["quantity_lots"] = 2
    with pytest.raises(EventModelError, match="cumulative"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[5])
    event["payload"]["fee_schedule_id"] = ""
    with pytest.raises(EventModelError, match="fee_schedule_id"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[8])
    event["payload"]["rule_id"] = ""
    with pytest.raises(EventModelError, match="rule_id"):
        validate_event_document(event)


def test_audit_writer_and_verifier(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    verification = write_audit_log(path, "step5-sample-run", sample_events())
    assert verification.records == 9
    assert verification.run_id == "step5-sample-run"
    assert len(verification.final_sha256) == 64

    with pytest.raises(FileExistsError):
        AuditLogWriter(path, "step5-sample-run")

    writer = AuditLogWriter(tmp_path / "other.jsonl", "different-run")
    with pytest.raises(EventModelError, match="run_id"):
        writer.append(sample_events()[0])


def test_audit_verifier_detects_tampering_and_chain_errors(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_audit_log(path, "step5-sample-run", sample_events())
    records: list[dict[str, Any]] = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["event"]["payload"]["bids"][0]["quantity_lots"] = 999
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    with pytest.raises(EventModelError, match="hash mismatch"):
        verify_audit_log(path)

    path.write_text("\n", encoding="utf-8")
    with pytest.raises(EventModelError, match="empty record"):
        verify_audit_log(path)


def test_event_model_sample_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = write_event_model_sample(first)
    second_manifest = write_event_model_sample(second)
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    for filename in ("instrument.json", "episode.json", "events.jsonl", "audit.jsonl"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    assert verify_audit_log(first / "audit.jsonl").records == 9


def _base_event(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = copy.deepcopy(sample_events()[0])
    event["kind"] = kind
    event["payload"] = payload
    return event


def test_validator_covers_timestamp_schema_and_type_failures() -> None:
    with pytest.raises(EventModelError, match="object"):
        validate_event_document([])  # type: ignore[arg-type]

    event = copy.deepcopy(sample_events()[0])
    event["schema_version"]["major"] = 2
    with pytest.raises(EventModelError, match="unsupported schema"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["event_id"] = True
    with pytest.raises(EventModelError, match="integer"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["event_time"]["domain"] = "monotonic-local"
    with pytest.raises(EventModelError, match="domain"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["receive_time"] = None
    event["available_time"] = None
    validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["ordering"]["canonical_sequence"] = 0
    with pytest.raises(EventModelError, match="canonical_sequence"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["ordering"]["has_source_sequence"] = "yes"
    with pytest.raises(EventModelError, match="boolean"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["payload"]["bids"] = "not-an-array"
    with pytest.raises(EventModelError, match="array"):
        validate_event_document(event)


def test_depth_trade_timer_and_market_order_payloads() -> None:
    depth = _base_event(
        "depth_update",
        {
            "side": "buy",
            "price_ticks": 100,
            "quantity_after_lots": 3,
            "action": "set",
            "order_count_after": None,
        },
    )
    validate_event_document(depth)
    depth["payload"]["side"] = "middle"
    with pytest.raises(EventModelError, match="side"):
        validate_event_document(depth)
    depth["payload"] = {
        "side": "sell",
        "price_ticks": 101,
        "quantity_after_lots": 0,
        "action": "set",
        "order_count_after": None,
    }
    with pytest.raises(EventModelError, match="positive quantity"):
        validate_event_document(depth)
    depth["payload"]["action"] = "delete"
    validate_event_document(depth)
    depth["payload"]["quantity_after_lots"] = 2
    with pytest.raises(EventModelError, match="zero quantity"):
        validate_event_document(depth)
    depth["payload"]["action"] = "delta"
    with pytest.raises(EventModelError, match="unsupported"):
        validate_event_document(depth)

    trade = _base_event(
        "trade",
        {"trade_id": 1, "price_ticks": 100, "quantity_lots": 2, "aggressor_side": "buy"},
    )
    validate_event_document(trade)

    timer = _base_event("timer", {"timer_name": "grid", "occurrence": 0})
    validate_event_document(timer)
    timer["payload"]["timer_name"] = ""
    with pytest.raises(EventModelError, match="timer_name"):
        validate_event_document(timer)

    market = copy.deepcopy(sample_events()[2])
    market["payload"]["order_type"] = "market"
    market["payload"]["limit_price_ticks"] = None
    market["payload"]["post_only"] = True
    with pytest.raises(EventModelError, match="post-only"):
        validate_event_document(market)
    market["payload"]["post_only"] = False
    validate_event_document(market)
    market["payload"]["order_type"] = "stop"
    with pytest.raises(EventModelError, match="order_type"):
        validate_event_document(market)


def test_rejection_and_replace_payload_identifier_paths() -> None:
    order_rejected = _base_event(
        "order_rejected",
        {"client_order_id": 1, "reason": "invalid_price", "detail": "bad"},
    )
    validate_event_document(order_rejected)

    replace_request = _base_event(
        "replace_request",
        {
            "client_order_id": 1,
            "exchange_order_id": 2,
            "replacement_client_order_id": 3,
            "decision_id": 4,
            "new_quantity_lots": 2,
            "new_limit_price_ticks": 99,
            "decision_time": {"domain": "simulation", "ns": 1},
            "outbound_send_time": {"domain": "simulation", "ns": 2},
            "exchange_receive_time": {"domain": "simulation", "ns": 3},
        },
    )
    validate_event_document(replace_request)

    replace_ack = _base_event(
        "replace_acknowledged",
        {
            "original_client_order_id": 1,
            "original_exchange_order_id": 2,
            "replacement_client_order_id": 3,
            "replacement_exchange_order_id": 4,
            "accepted_quantity_lots": 2,
            "leaves_quantity_lots": 2,
        },
    )
    validate_event_document(replace_ack)

    replace_rejected = _base_event(
        "replace_rejected",
        {
            "client_order_id": 1,
            "exchange_order_id": 2,
            "replacement_client_order_id": 3,
            "reason": "invalid_state",
            "resulting_state": "live",
            "detail": "unchanged",
        },
    )
    validate_event_document(replace_rejected)


def test_event_envelope_rejects_clock_and_kind_errors() -> None:
    event = copy.deepcopy(sample_events()[0])
    event["receive_time"]["domain"] = "unix_utc"
    with pytest.raises(EventModelError, match="different clocks"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["receive_time"] = None
    with pytest.raises(EventModelError, match="requires receive_time"):
        validate_event_document(event)

    event = copy.deepcopy(sample_events()[0])
    event["kind"] = "unknown"
    with pytest.raises(EventModelError, match="unsupported event kind"):
        validate_event_document(event)


def _load_audit_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_bytes(b"".join(canonical_json_bytes(record) + b"\n" for record in records))


def _rehash(record: dict[str, Any]) -> None:
    import hashlib

    material = dict(record)
    material.pop("record_sha256", None)
    record["record_sha256"] = hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def test_audit_verifier_all_structural_failures(tmp_path: Path) -> None:
    with pytest.raises(EventModelError, match="non-empty"):
        AuditLogWriter(tmp_path / "empty-run.jsonl", "")

    base = tmp_path / "base.jsonl"
    write_audit_log(base, "step5-sample-run", sample_events()[:2])

    records = _load_audit_records(base)
    records[1]["run_id"] = "another-run"
    _rehash(records[1])
    path = tmp_path / "multi-run.jsonl"
    _write_records(path, records)
    with pytest.raises(EventModelError, match="multiple run_id"):
        verify_audit_log(path)

    records = _load_audit_records(base)
    records[1]["append_index"] = 3
    _rehash(records[1])
    path = tmp_path / "index.jsonl"
    _write_records(path, records)
    with pytest.raises(EventModelError, match="append_index"):
        verify_audit_log(path)

    records = _load_audit_records(base)
    records[1]["previous_record_sha256"] = "f" * 64
    _rehash(records[1])
    path = tmp_path / "chain.jsonl"
    _write_records(path, records)
    with pytest.raises(EventModelError, match="previous hash"):
        verify_audit_log(path)

    records = _load_audit_records(base)
    records[0]["record_sha256"] = "UPPER"
    path = tmp_path / "hash-format.jsonl"
    _write_records(path, records)
    with pytest.raises(EventModelError, match="lowercase"):
        verify_audit_log(path)

    records = _load_audit_records(base)
    records[0]["event"]["run_id"] = "wrong-event-run"
    _rehash(records[0])
    records[1]["previous_record_sha256"] = records[0]["record_sha256"]
    _rehash(records[1])
    path = tmp_path / "event-run.jsonl"
    _write_records(path, records)
    with pytest.raises(EventModelError, match="event run_id"):
        verify_audit_log(path)
