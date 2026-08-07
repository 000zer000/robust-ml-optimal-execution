"""Immutable Step 21 prediction feature/label artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from robust_execution import __version__
from robust_execution.canonical_data.models import write_columnar_table
from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.prediction.builder import build_feature_label_rows
from robust_execution.prediction.config import PredictionFeatureConfig
from robust_execution.prediction.models import DecisionPoint, PredictionMarketEvent


FEATURE_NAMES = (
    "spread_ticks",
    "same_top1_lots",
    "opposite_top1_lots",
    "same_top5_lots",
    "opposite_top5_lots",
    "side_imbalance_top1_bps",
    "side_imbalance_top5_bps",
    "toward_quote_trade_flow_250ms_lots",
    "toward_quote_trade_flow_1s_lots",
    "toward_quote_trade_flow_5s_lots",
    "trade_count_1s",
    "trade_count_5s",
    "side_mid_move_250ms_half_ticks",
    "side_mid_move_1s_half_ticks",
    "side_mid_move_5s_half_ticks",
    "realized_abs_mid_move_1s_half_ticks",
    "realized_abs_mid_move_5s_half_ticks",
    "spread_change_1s_ticks",
    "quote_age_ns",
    "time_since_last_trade_ns",
)


def feature_dictionary() -> dict[str, object]:
    definitions = {
        "spread_ticks": "best_ask_ticks - best_bid_ticks",
        "same_top1_lots": "displayed lots at the passive-side best quote",
        "opposite_top1_lots": "displayed lots at the opposite best quote",
        "same_top5_lots": "sum of passive-side displayed lots across configured top levels",
        "opposite_top5_lots": "sum of opposite-side displayed lots across configured top levels",
        "side_imbalance_top1_bps": (
            "10000*(same_top1-opposite_top1)/(same_top1+opposite_top1), "
            "truncated toward zero"
        ),
        "side_imbalance_top5_bps": (
            "10000*(same_top5-opposite_top5)/(same_top5+opposite_top5), "
            "truncated toward zero"
        ),
        "toward_quote_trade_flow_250ms_lots": (
            "side-normalized signed aggressor flow over (cutoff-250ms, cutoff]"
        ),
        "toward_quote_trade_flow_1s_lots": (
            "side-normalized signed aggressor flow over (cutoff-1s, cutoff]"
        ),
        "toward_quote_trade_flow_5s_lots": (
            "side-normalized signed aggressor flow over (cutoff-5s, cutoff]"
        ),
        "trade_count_1s": "trade count over (cutoff-1s, cutoff]",
        "trade_count_5s": "trade count over (cutoff-5s, cutoff]",
        "side_mid_move_250ms_half_ticks": (
            "side_sign*(current_mid_x2-past_mid_x2) at 250ms lookback"
        ),
        "side_mid_move_1s_half_ticks": "side_sign*(current_mid_x2-past_mid_x2) at 1s lookback",
        "side_mid_move_5s_half_ticks": "side_sign*(current_mid_x2-past_mid_x2) at 5s lookback",
        "realized_abs_mid_move_1s_half_ticks": "sum absolute mid_x2 changes over the trailing 1s",
        "realized_abs_mid_move_5s_half_ticks": "sum absolute mid_x2 changes over the trailing 5s",
        "spread_change_1s_ticks": "current spread minus spread at 1s lookback",
        "quote_age_ns": (
            "source cutoff minus time the current passive-side best price became current"
        ),
        "time_since_last_trade_ns": (
            "source cutoff minus latest causal trade time; censored at max_window+1 if none"
        ),
    }
    return {
        "schema_version": "prediction-feature-dictionary-v1",
        "feature_count": len(FEATURE_NAMES),
        "feature_names": list(FEATURE_NAMES),
        "all_features_causal": True,
        "uses_exact_historical_queue_position": False,
        "uses_future_volume_profile": False,
        "definitions": definitions,
    }


def _table_schema(name: str, columns: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "table_name": name,
        "columns": [
            {"name": column, "logical_type": "int64_or_utf8", "nullable": False}
            for column in columns
        ],
    }


def _event_to_dict(event: PredictionMarketEvent) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "symbol": event.symbol,
        "kind": event.kind,
        "event_time_ns": event.event_time_ns,
        "available_time_ns": event.available_time_ns,
        "bids": [list(item) for item in event.bids],
        "asks": [list(item) for item in event.asks],
        "updates": [
            {
                "side": update.side,
                "price_ticks": update.price_ticks,
                "quantity_lots": update.quantity_lots,
            }
            for update in event.updates
        ],
        "trade_price_ticks": event.trade_price_ticks,
        "trade_quantity_lots": event.trade_quantity_lots,
        "buyer_is_maker": event.buyer_is_maker,
    }


def _decision_to_dict(point: DecisionPoint) -> dict[str, object]:
    return {
        "symbol": point.symbol,
        "decision_time_ns": point.decision_time_ns,
        "passive_side": point.passive_side,
    }


def write_prediction_fixture(
    config: PredictionFeatureConfig,
    events: list[PredictionMarketEvent],
    decisions: list[DecisionPoint],
    coverage_end_ns_by_symbol: dict[str, int],
    output_root: Path,
) -> Path:
    target = output_root / config.dataset_id
    if target.exists():
        raise FileExistsError(f"prediction dataset already exists: {target}")
    rows = build_feature_label_rows(events, decisions, coverage_end_ns_by_symbol, config)
    input_payload = {
        "schema_version": "prediction-input-fixture-v1",
        "events": [_event_to_dict(event) for event in events],
        "decisions": [_decision_to_dict(point) for point in decisions],
        "coverage_end_ns_by_symbol": coverage_end_ns_by_symbol,
    }
    input_path = target / "input-events.json"
    write_immutable_json(input_path, input_payload)
    feature_rows = [row.feature for row in rows]
    label_rows = [row.label for row in rows]
    feature_columns = tuple(feature_rows[0])
    label_columns = tuple(label_rows[0])
    feature_artifact = write_columnar_table(
        target,
        "prediction_features",
        feature_rows,
        _table_schema("prediction_features", feature_columns),
        feature_columns,
    )
    label_artifact = write_columnar_table(
        target,
        "prediction_labels",
        label_rows,
        _table_schema("prediction_labels", label_columns),
        label_columns,
    )
    dictionary = feature_dictionary()
    dictionary_path = target / "feature-dictionary.json"
    write_immutable_json(dictionary_path, dictionary)
    config_sha = hashlib.sha256(canonical_json_bytes(config.__dict__)).hexdigest()
    manifest: dict[str, Any] = {
        "schema_version": "prediction-dataset-manifest-v1",
        "step": 21,
        "dataset_id": config.dataset_id,
        "software_version": __version__,
        "symbols": list(config.symbols),
        "row_count": len(rows),
        "feature_count": len(FEATURE_NAMES),
        "feature_dictionary_sha256": hashlib.sha256(dictionary_path.read_bytes()).hexdigest(),
        "input_events_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "config_sha256": config_sha,
        "candidate_horizons_ns": list(config.candidate_horizons_ns),
        "selected_horizon": config.selected_horizon,
        "primary_target": config.primary_target,
        "secondary_target": config.secondary_target,
        "features_and_labels_physically_separated": True,
        "future_information_used_in_features": False,
        "exact_historical_queue_used": False,
        "research_admissible": False,
        "research_status": "synthetic_validation_only_non_research",
        "research_blockers": ["zero_admitted_live_days", "gate_c_not_open"],
        "tables": [feature_artifact.to_dict(), label_artifact.to_dict()],
    }
    manifest_path = target / "dataset-manifest.json"
    write_immutable_json(manifest_path, manifest)
    write_immutable_json(
        target / "dataset-manifest.sha256.json",
        {"sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
    )
    return manifest_path
