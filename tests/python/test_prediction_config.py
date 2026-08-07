from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_execution.prediction.config import PredictionConfigError, load_prediction_feature_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/models/step21_causal_features_sample.json"


def test_load_prediction_config() -> None:
    config = load_prediction_feature_config(CONFIG)
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.maximum_horizon_ns == 5_000_000_000
    assert config.maximum_feature_window_ns == 5_000_000_000
    assert config.top_levels == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "v2"),
        ("dataset_id", ""),
        ("symbols", ["BTCUSDT"]),
        ("symbols", ["BTCUSDT", "BTCUSDT"]),
        ("symbols", ["BTCUSDT", "ethusdt"]),
        ("observation_latency_ns", 0),
        ("candidate_horizons_ns", [250_000_000, 1_000_000_000]),
        ("feature_windows_ns", [1_000_000_000, 5_000_000_000]),
        ("feature_windows_ns", [250_000_000, 1_000_000_000, 1_000_000_000, 5_000_000_000]),
        ("top_levels", 4),
        ("selected_horizon", "1000ms"),
        ("primary_target", "price_up"),
        ("secondary_target", "something_else"),
        ("exact_historical_queue_allowed", True),
    ],
)
def test_reject_unsafe_prediction_config(tmp_path: Path, field: str, value: object) -> None:
    raw = json.loads(CONFIG.read_text())
    raw[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(path)


def test_reject_missing_extra_non_object_and_bad_json(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    raw.pop("top_levels")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(path)
    raw = json.loads(CONFIG.read_text())
    raw["extra"] = 1
    path.write_text(json.dumps(raw))
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(path)
    path.write_text("[]")
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(path)
    path.write_text("{")
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(path)
    with pytest.raises(PredictionConfigError):
        load_prediction_feature_config(tmp_path / "missing.json")
