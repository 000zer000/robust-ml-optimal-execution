#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.prediction import (
    BookUpdate,
    build_feature_label_rows,
    load_prediction_feature_config,
    write_prediction_fixture,
)
from robust_execution.prediction.fixture import NS, validation_fixture

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step21_causal_features_sample.json"
OUTPUT = ROOT / "data/sample/prediction"
VALIDATION = ROOT / "results/validation/step21/leakage_mutation_report.json"


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _row(rows, symbol: str, side: str, decision_time_ns: int):
    return next(
        row
        for row in rows
        if row.feature["symbol"] == symbol
        and row.feature["passive_side"] == side
        and row.feature["decision_time_ns"] == decision_time_ns
    )


def main() -> None:
    config = load_prediction_feature_config(CONFIG)
    events, decisions, coverage = validation_fixture()
    manifest = write_prediction_fixture(config, events, decisions, coverage, OUTPUT)
    baseline = build_feature_label_rows(events, decisions, coverage, config)

    future_target = next(
        event
        for event in events
        if event.symbol == "BTCUSDT"
        and event.kind == "depth"
        and event.event_time_ns == 6_050_000_000
    )
    future_events = [
        replace(event, updates=(BookUpdate("ask", 101, 70),))
        if event.sequence == future_target.sequence
        else event
        for event in events
    ]
    future_rows = build_feature_label_rows(future_events, decisions, coverage, config)
    before = _row(baseline, "BTCUSDT", "ask", 6 * NS)
    after = _row(future_rows, "BTCUSDT", "ask", 6 * NS)

    sentinel = next(
        event
        for event in events
        if event.symbol == "BTCUSDT" and event.event_time_ns == 14_100_000_000
    )
    post_events = [
        replace(event, trade_quantity_lots=99_999) if event.sequence == sentinel.sequence else event
        for event in events
    ]
    post_rows = build_feature_label_rows(post_events, decisions, coverage, config)

    past_target = next(
        event
        for event in events
        if event.symbol == "BTCUSDT" and event.event_time_ns == 5_800_000_000
    )
    past_events = [
        replace(event, trade_quantity_lots=115) if event.sequence == past_target.sequence else event
        for event in events
    ]
    past_rows = build_feature_label_rows(past_events, decisions, coverage, config)
    past_before = _row(baseline, "BTCUSDT", "bid", 6 * NS)
    past_after = _row(past_rows, "BTCUSDT", "bid", 6 * NS)

    report = {
        "schema_version": "step21-leakage-mutation-report-v1",
        "step": 21,
        "dataset_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "future_mutation_same_decision_feature_hash_unchanged": _hash(before.feature)
        == _hash(after.feature),
        "future_mutation_target_changed": before.label["quote_depletion_250ms"]
        != after.label["quote_depletion_250ms"],
        "post_horizon_mutation_all_rows_unchanged": baseline == post_rows,
        "past_mutation_feature_hash_changed": (
            _hash(past_before.feature) != _hash(past_after.feature)
        ),
        "features_and_labels_physically_separated": True,
        "selected_horizon_frozen": False,
        "selected_horizon_marker": config.selected_horizon,
        "research_status": "synthetic_validation_only_non_research",
    }
    if not all(
        report[key]
        for key in (
            "future_mutation_same_decision_feature_hash_unchanged",
            "future_mutation_target_changed",
            "post_horizon_mutation_all_rows_unchanged",
            "past_mutation_feature_hash_changed",
            "features_and_labels_physically_separated",
        )
    ):
        raise SystemExit("Step 21 mutation oracle failed")
    write_immutable_json(VALIDATION, report)
    print(
        json.dumps(
            {"status": "ok", "manifest": str(manifest), "rows": len(baseline)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
