"""Deterministic, non-empirical sample documents for the Step 5 event model."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from robust_execution.event_model import canonical_json_bytes, write_audit_log


def _timestamp(value: int) -> dict[str, Any]:
    return {"domain": "simulation", "ns": value}


def _header(event_id: int, exchange_ns: int, *, origin: str, channel: str) -> dict[str, Any]:
    return {
        "schema_version": {"major": 1, "minor": 0},
        "event_id": event_id,
        "run_id": "step5-sample-run",
        "venue": "synthetic",
        "instrument": "TEST-USD",
        "source_channel": channel,
        "origin": origin,
        "event_time": _timestamp(exchange_ns),
        "receive_time": _timestamp(exchange_ns + 10),
        "available_time": _timestamp(exchange_ns + 20),
        "ordering": {
            "has_source_sequence": True,
            "source_sequence": event_id,
            "source_subsequence": 0,
            "ingest_sequence": event_id,
            "canonical_sequence": event_id,
        },
        "original_timestamp": None,
    }


def sample_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.append(
        {
            **_header(1, 1_000, origin="synthetic_exchange", channel="book"),
            "kind": "book_snapshot",
            "payload": {
                "bids": [{"price_ticks": 100, "quantity_lots": 10, "order_count": 2}],
                "asks": [{"price_ticks": 101, "quantity_lots": 12, "order_count": 3}],
            },
        }
    )
    events.append(
        {
            **_header(2, 1_100, origin="strategy", channel="decision"),
            "kind": "decision",
            "payload": {
                "decision_id": 1,
                "strategy_id": "sample-policy-v1",
                "observation_cutoff": _timestamp(1_020),
                "decision_start": _timestamp(1_050),
                "decision_end": _timestamp(1_060),
                "remaining_inventory_lots": 3,
                "action_name": "submit_passive_buy",
                "model_artifact_id": None,
            },
        }
    )
    events.append(
        {
            **_header(3, 1_200, origin="strategy", channel="orders"),
            "kind": "order_submit",
            "payload": {
                "parent_order_id": 1,
                "client_order_id": 1,
                "decision_id": 1,
                "side": "buy",
                "order_type": "limit",
                "time_in_force": "gtc",
                "quantity_lots": 2,
                "limit_price_ticks": 100,
                "post_only": True,
                "decision_time": _timestamp(1_060),
                "outbound_send_time": _timestamp(1_070),
                "exchange_receive_time": _timestamp(1_200),
            },
        }
    )
    events.append(
        {
            **_header(4, 1_210, origin="synthetic_exchange", channel="orders"),
            "kind": "order_acknowledged",
            "payload": {
                "client_order_id": 1,
                "exchange_order_id": 1001,
                "external_order_id": None,
                "accepted_quantity_lots": 2,
                "cumulative_filled_lots": 0,
                "leaves_quantity_lots": 2,
                "state": "live",
            },
        }
    )
    events.append(
        {
            **_header(5, 1_300, origin="synthetic_exchange", channel="fills"),
            "kind": "fill",
            "payload": {
                "execution_id": 1,
                "client_order_id": 1,
                "exchange_order_id": 1001,
                "external_match_id": "sample-match-1",
                "side": "buy",
                "price_ticks": 100,
                "quantity_lots": 1,
                "cumulative_filled_lots": 1,
                "leaves_quantity_lots": 1,
                "liquidity_role": "maker",
            },
        }
    )
    events.append(
        {
            **_header(6, 1_300, origin="synthetic_exchange", channel="fees"),
            "kind": "fee",
            "payload": {
                "execution_id": 1,
                "fee_schedule_id": "sample-fees-v1",
                "amount_quote_atoms": -1,
                "liquidity_role": "maker",
            },
        }
    )
    events.append(
        {
            **_header(7, 1_400, origin="strategy", channel="orders"),
            "kind": "cancel_request",
            "payload": {
                "client_order_id": 1,
                "exchange_order_id": 1001,
                "decision_id": 2,
                "decision_time": _timestamp(1_350),
                "outbound_send_time": _timestamp(1_360),
                "exchange_receive_time": _timestamp(1_400),
            },
        }
    )
    events.append(
        {
            **_header(8, 1_410, origin="synthetic_exchange", channel="orders"),
            "kind": "cancel_acknowledged",
            "payload": {
                "client_order_id": 1,
                "exchange_order_id": 1001,
                "cumulative_filled_lots": 1,
                "cancelled_quantity_lots": 1,
                "leaves_quantity_lots": 0,
                "state": "cancelled",
            },
        }
    )
    events.append(
        {
            **_header(9, 2_000, origin="system", channel="terminal"),
            "kind": "terminal_completion",
            "payload": {
                "parent_order_id": 1,
                "side": "buy",
                "quantity_lots": 2,
                "price_ticks": 102,
                "explicit_fee_quote_atoms": 2,
                "rule_id": "common-terminal-aggressive-v1",
            },
        }
    )
    return events


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(document) + b"\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_event_model_sample(output_directory: Path) -> Path:
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="event-model-sample-", dir=output_directory.parent
    ) as temporary:
        staging = Path(temporary)
        instrument = {
            "schema_version": {"major": 1, "minor": 0},
            "venue": "synthetic",
            "instrument": "TEST-USD",
            "base_asset": "TEST",
            "quote_asset": "USD",
            "tick_size": {"numerator": 1, "denominator": 100},
            "lot_size": {"numerator": 1, "denominator": 1000},
            "quote_atom_size": {"numerator": 1, "denominator": 100},
            "minimum_order_quantity_lots": 1,
            "maximum_order_quantity_lots": 1_000_000,
            "metadata_version": "step5-synthetic-v1",
        }
        episode = {
            "schema_version": {"major": 1, "minor": 0},
            "episode_id": "step5-sample-episode",
            "run_id": "step5-sample-run",
            "venue": "synthetic",
            "instrument": "TEST-USD",
            "side": "buy",
            "arrival_time": _timestamp(1_000),
            "deadline_time": _timestamp(2_000),
            "parent_quantity_lots": 3,
            "arrival_benchmark_ticks": 101,
            "strategy_id": "sample-policy",
            "strategy_version": "1",
            "queue_model_id": "exact-fifo",
            "latency_model_id": "sample-latency-v1",
            "fee_schedule_id": "sample-fees-v1",
            "impact_mode": "synthetic-exact-sample",
            "random_seed": 0,
            "code_commit": "non-empirical-step5-sample",
            "data_hashes": {"synthetic_input": "0" * 64},
        }
        _write_json(staging / "instrument.json", instrument)
        _write_json(staging / "episode.json", episode)
        events = sample_events()
        with (staging / "events.jsonl").open("wb") as handle:
            for event in events:
                handle.write(canonical_json_bytes(event) + b"\n")
        write_audit_log(staging / "audit.jsonl", "step5-sample-run", events)
        artifact_paths = [
            staging / "instrument.json",
            staging / "episode.json",
            staging / "events.jsonl",
            staging / "audit.jsonl",
        ]
        manifest = {
            "schema_version": 1,
            "research_claim": None,
            "description": "Deterministic non-empirical Step 5 event-model fixture",
            "artifacts": {path.name: _sha256(path) for path in artifact_paths},
        }
        _write_json(staging / "manifest.json", manifest)

        output_directory.mkdir(parents=True, exist_ok=True)
        for staged_path in sorted(staging.iterdir()):
            os.replace(staged_path, output_directory / staged_path.name)
    return output_directory / "manifest.json"
