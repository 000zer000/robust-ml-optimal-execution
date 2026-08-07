"""Strict Step 21 causal-feature and target configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class PredictionConfigError(ValueError):
    """Raised when a Step 21 prediction-data contract is unsafe or incomplete."""


@dataclass(frozen=True)
class PredictionFeatureConfig:
    schema_version: str
    dataset_id: str
    symbols: tuple[str, ...]
    observation_latency_ns: int
    candidate_horizons_ns: tuple[int, ...]
    feature_windows_ns: tuple[int, ...]
    top_levels: int
    selected_horizon: str
    primary_target: str
    secondary_target: str
    research_admissible_input_required: bool
    exact_historical_queue_allowed: bool

    @property
    def maximum_horizon_ns(self) -> int:
        return max(self.candidate_horizons_ns)

    @property
    def maximum_feature_window_ns(self) -> int:
        return max(self.feature_windows_ns)


def _required(raw: dict[str, Any], key: str, expected: type[Any]) -> Any:
    value = raw.get(key)
    if not isinstance(value, expected):
        raise PredictionConfigError(f"{key} must be {expected.__name__}")
    return value


def _strict_keys(raw: dict[str, Any], expected: set[str]) -> None:
    if set(raw) != expected:
        missing = sorted(expected - set(raw))
        extra = sorted(set(raw) - expected)
        raise PredictionConfigError(
            f"prediction config keys differ; missing={missing}, extra={extra}"
        )


def load_prediction_feature_config(path: Path) -> PredictionFeatureConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionConfigError(f"cannot read prediction config: {exc}") from exc
    if not isinstance(raw, dict):
        raise PredictionConfigError("prediction config must be an object")
    _strict_keys(
        raw,
        {
            "schema_version",
            "dataset_id",
            "symbols",
            "observation_latency_ns",
            "candidate_horizons_ns",
            "feature_windows_ns",
            "top_levels",
            "selected_horizon",
            "primary_target",
            "secondary_target",
            "research_admissible_input_required",
            "exact_historical_queue_allowed",
        },
    )
    symbols_raw = _required(raw, "symbols", list)
    horizons_raw = _required(raw, "candidate_horizons_ns", list)
    windows_raw = _required(raw, "feature_windows_ns", list)
    config = PredictionFeatureConfig(
        schema_version=str(_required(raw, "schema_version", str)),
        dataset_id=str(_required(raw, "dataset_id", str)),
        symbols=tuple(str(item) for item in symbols_raw),
        observation_latency_ns=int(_required(raw, "observation_latency_ns", int)),
        candidate_horizons_ns=tuple(int(item) for item in horizons_raw),
        feature_windows_ns=tuple(int(item) for item in windows_raw),
        top_levels=int(_required(raw, "top_levels", int)),
        selected_horizon=str(_required(raw, "selected_horizon", str)),
        primary_target=str(_required(raw, "primary_target", str)),
        secondary_target=str(_required(raw, "secondary_target", str)),
        research_admissible_input_required=bool(
            _required(raw, "research_admissible_input_required", bool)
        ),
        exact_historical_queue_allowed=bool(
            _required(raw, "exact_historical_queue_allowed", bool)
        ),
    )
    if config.schema_version != "prediction-feature-config-v1" or not config.dataset_id:
        raise PredictionConfigError("unsupported schema or empty dataset_id")
    if len(config.symbols) < 2 or len(config.symbols) != len(set(config.symbols)):
        raise PredictionConfigError("Step 21 requires at least two unique symbols")
    if any(not symbol or symbol != symbol.upper() for symbol in config.symbols):
        raise PredictionConfigError("symbols must be non-empty uppercase strings")
    if config.observation_latency_ns <= 0:
        raise PredictionConfigError("observation_latency_ns must be positive")
    if config.candidate_horizons_ns != (250_000_000, 1_000_000_000, 5_000_000_000):
        raise PredictionConfigError("candidate horizons must remain 250 ms, 1 s, and 5 s")
    if (
        not config.feature_windows_ns
        or config.feature_windows_ns != tuple(sorted(set(config.feature_windows_ns)))
        or any(value <= 0 for value in config.feature_windows_ns)
        or 250_000_000 not in config.feature_windows_ns
        or 1_000_000_000 not in config.feature_windows_ns
        or 5_000_000_000 not in config.feature_windows_ns
    ):
        raise PredictionConfigError(
            "feature windows must be sorted positive and include 250 ms/1 s/5 s"
        )
    if config.top_levels != 5:
        raise PredictionConfigError("Step 21 frozen feature set requires top_levels == 5")
    if config.selected_horizon != "PRE_DATA_FIELD_BEFORE_CALIBRATION":
        raise PredictionConfigError("Step 21 cannot preselect the final prediction horizon")
    if config.primary_target != "best_quote_depletion_or_trade_through":
        raise PredictionConfigError("primary target changed")
    if config.secondary_target != "side_signed_post_event_adverse_selection":
        raise PredictionConfigError("secondary target changed")
    if config.exact_historical_queue_allowed:
        raise PredictionConfigError("Step 21 cannot use exact historical queue position")
    return config
