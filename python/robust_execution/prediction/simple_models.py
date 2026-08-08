"""Step 22 leakage-safe simple prediction models and diagnostics.

This module deliberately separates development, calibration, and evaluation data.
The synthetic engineering mode exercises the machinery without opening the locked
historical research test. Research mode requires a previously frozen horizon.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import random
import statistics
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.prediction.artifacts import FEATURE_NAMES

ModelFamily = Literal["base_rate", "logistic", "gradient_boosted_trees", "simple_mlp"]
SplitName = Literal["train", "validation", "calibration", "engineering_holdout"]

HORIZON_TARGETS: dict[str, str] = {
    "250ms": "quote_depletion_250ms",
    "1s": "quote_depletion_1s",
    "5s": "quote_depletion_5s",
}


class SimpleModelError(RuntimeError):
    """Raised when Step 22 training would violate its frozen data protocol."""


def _fit_single_worker(estimator: Any, x: np.ndarray, y: np.ndarray) -> Any:
    """Fit without leaking a process-wide job-discovery override to callers."""
    previous = os.environ.get("LOKY_MAX_CPU_COUNT")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    try:
        return estimator.fit(x, y)
    finally:
        if previous is None:
            os.environ.pop("LOKY_MAX_CPU_COUNT", None)


@dataclass(frozen=True)
class SplitDays:
    train: int
    validation: int
    calibration: int
    engineering_holdout: int

    @property
    def total(self) -> int:
        return self.train + self.validation + self.calibration + self.engineering_holdout


@dataclass(frozen=True)
class SimpleModelConfig:
    schema_version: str
    dataset_id: str
    symbols: tuple[str, ...]
    feature_names: tuple[str, ...]
    candidate_horizons: tuple[str, ...]
    selected_horizon: str
    mode: Literal["engineering_fixture", "research"]
    split_days: SplitDays
    rows_per_symbol_side_day: int
    random_seed: int
    calibration_method: str
    ece_bins: int
    precision_recall_thresholds: tuple[float, ...]
    logistic_c: tuple[float, ...]
    boosted_learning_rate: tuple[float, ...]
    boosted_max_leaf_nodes: tuple[int, ...]
    mlp_hidden_units: tuple[int, ...]
    mlp_alpha: tuple[float, ...]
    final_model_selection_allowed: bool
    use_evaluation_for_selection: bool

    @property
    def total_days(self) -> int:
        return self.split_days.total


@dataclass(frozen=True)
class TrainingRow:
    row_id: str
    symbol: str
    passive_side: Literal["bid", "ask"]
    day_index: int
    decision_index: int
    feature: dict[str, int]
    labels: dict[str, int]


@dataclass(frozen=True)
class ProbabilityMetrics:
    rows: int
    positives: int
    prevalence: float
    log_loss: float
    brier: float
    ece: float
    roc_auc: float | None
    pr_auc: float | None
    calibration_intercept: float | None
    calibration_slope: float | None
    threshold_metrics: dict[str, dict[str, float]]


@dataclass(frozen=True)
class PlattCalibrator:
    intercept: float
    slope: float
    epsilon: float = 1e-9

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        p = np.clip(np.asarray(probabilities, dtype=np.float64), self.epsilon, 1.0 - self.epsilon)
        z = np.log(p / (1.0 - p))
        logits = self.intercept + self.slope * z
        logits = np.clip(logits, -40.0, 40.0)
        return 1.0 / (1.0 + np.exp(-logits))


@dataclass
class TrainOnlyScaledEstimator:
    scaler: StandardScaler
    classifier: object

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        transformed = self.scaler.transform(matrix)
        return self.classifier.predict_proba(transformed)  # type: ignore[union-attr]


@dataclass
class FittedSimpleModel:
    family: ModelFamily
    horizon: str
    hyperparameters: dict[str, object]
    estimator: object | None
    constant_probability: float | None
    calibrator: PlattCalibrator | None
    train_prevalence: float
    feature_names: tuple[str, ...]

    def predict_uncalibrated(self, matrix: np.ndarray) -> np.ndarray:
        if self.family == "base_rate":
            if self.constant_probability is None:
                raise SimpleModelError("base-rate model lacks its constant probability")
            return np.full(matrix.shape[0], self.constant_probability, dtype=np.float64)
        if self.estimator is None or not hasattr(self.estimator, "predict_proba"):
            raise SimpleModelError("fitted estimator lacks predict_proba")
        probabilities = self.estimator.predict_proba(matrix)[:, 1]  # type: ignore[union-attr]
        return np.asarray(probabilities, dtype=np.float64)

    def predict_calibrated(self, matrix: np.ndarray) -> np.ndarray:
        raw = self.predict_uncalibrated(matrix)
        if self.calibrator is None:
            return raw
        return self.calibrator.predict(raw)


def _strict_keys(raw: dict[str, Any], expected: set[str]) -> None:
    if set(raw) != expected:
        raise SimpleModelError(
            f"Step 22 config keys differ; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _numeric_tuple(raw: object, name: str, cast: type[float] | type[int]) -> tuple[Any, ...]:
    if not isinstance(raw, list) or not raw:
        raise SimpleModelError(f"{name} must be a non-empty list")
    result = tuple(cast(value) for value in raw)
    if any(value <= 0 for value in result):
        raise SimpleModelError(f"{name} values must be positive")
    return result


def load_simple_model_config(path: Path) -> SimpleModelConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimpleModelError(f"cannot read Step 22 config: {exc}") from exc
    if not isinstance(raw, dict):
        raise SimpleModelError("Step 22 config must be an object")
    expected = {
        "schema_version",
        "dataset_id",
        "symbols",
        "feature_names",
        "candidate_horizons",
        "selected_horizon",
        "mode",
        "split_days",
        "rows_per_symbol_side_day",
        "random_seed",
        "calibration_method",
        "ece_bins",
        "precision_recall_thresholds",
        "hyperparameters",
        "final_model_selection_allowed",
        "use_evaluation_for_selection",
    }
    _strict_keys(raw, expected)
    if raw["schema_version"] != "simple-model-training-config-v1":
        raise SimpleModelError("unsupported Step 22 config schema")
    symbols = raw["symbols"]
    features = raw["feature_names"]
    horizons = raw["candidate_horizons"]
    if not isinstance(symbols, list) or tuple(symbols) != ("BTCUSDT", "ETHUSDT"):
        raise SimpleModelError("Step 22 symbols must remain BTCUSDT and ETHUSDT")
    if not isinstance(features, list) or tuple(features) != FEATURE_NAMES:
        raise SimpleModelError(
            "Step 22 feature set must exactly match the frozen Step 21 dictionary"
        )
    if not isinstance(horizons, list) or tuple(horizons) != ("250ms", "1s", "5s"):
        raise SimpleModelError("Step 22 candidate horizons must remain 250ms, 1s and 5s")
    selected = raw["selected_horizon"]
    mode = raw["mode"]
    if mode not in {"engineering_fixture", "research"}:
        raise SimpleModelError("mode must be engineering_fixture or research")
    if mode == "engineering_fixture":
        if selected != "PRE_DATA_FIELD_BEFORE_CALIBRATION":
            raise SimpleModelError("engineering fixture must not freeze the research horizon")
    elif selected not in horizons:
        raise SimpleModelError("research mode requires a previously frozen candidate horizon")
    if raw["final_model_selection_allowed"] is not False:
        raise SimpleModelError("Step 22 may not perform final model-family selection")
    if raw["use_evaluation_for_selection"] is not False:
        raise SimpleModelError("evaluation labels may never be used for model selection")
    split_raw = raw["split_days"]
    if not isinstance(split_raw, dict):
        raise SimpleModelError("split_days must be an object")
    _strict_keys(split_raw, {"train", "validation", "calibration", "engineering_holdout"})
    split = SplitDays(
        *(
            int(split_raw[key])
            for key in ("train", "validation", "calibration", "engineering_holdout")
        )
    )
    if (
        split.train,
        split.validation,
        split.calibration,
        split.engineering_holdout,
    ) != (50, 20, 10, 20):
        raise SimpleModelError("Step 22 engineering split must mirror 50/20/10/20 whole days")
    rows_per = raw["rows_per_symbol_side_day"]
    if not isinstance(rows_per, int) or rows_per < 1:
        raise SimpleModelError("rows_per_symbol_side_day must be positive")
    seed = raw["random_seed"]
    ece_bins = raw["ece_bins"]
    if not isinstance(seed, int) or seed < 0 or not isinstance(ece_bins, int) or ece_bins < 2:
        raise SimpleModelError("random_seed/ece_bins are invalid")
    if raw["calibration_method"] != "platt_logit":
        raise SimpleModelError("Step 22 calibration method must be platt_logit")
    thresholds_raw = raw["precision_recall_thresholds"]
    if not isinstance(thresholds_raw, list) or not thresholds_raw:
        raise SimpleModelError("precision_recall_thresholds must be non-empty")
    thresholds = tuple(float(value) for value in thresholds_raw)
    if any(not 0.0 < value < 1.0 for value in thresholds) or (
        tuple(sorted(set(thresholds))) != thresholds
    ):
        raise SimpleModelError("probability thresholds must be unique, increasing and inside (0,1)")
    hyper = raw["hyperparameters"]
    if not isinstance(hyper, dict):
        raise SimpleModelError("hyperparameters must be an object")
    _strict_keys(
        hyper,
        {
            "logistic_c",
            "boosted_learning_rate",
            "boosted_max_leaf_nodes",
            "mlp_hidden_units",
            "mlp_alpha",
        },
    )
    return SimpleModelConfig(
        schema_version=raw["schema_version"],
        dataset_id=str(raw["dataset_id"]),
        symbols=tuple(symbols),
        feature_names=tuple(features),
        candidate_horizons=tuple(horizons),
        selected_horizon=str(selected),
        mode=mode,
        split_days=split,
        rows_per_symbol_side_day=rows_per,
        random_seed=seed,
        calibration_method=raw["calibration_method"],
        ece_bins=ece_bins,
        precision_recall_thresholds=thresholds,
        logistic_c=_numeric_tuple(hyper["logistic_c"], "logistic_c", float),
        boosted_learning_rate=_numeric_tuple(
            hyper["boosted_learning_rate"], "boosted_learning_rate", float
        ),
        boosted_max_leaf_nodes=_numeric_tuple(
            hyper["boosted_max_leaf_nodes"], "boosted_max_leaf_nodes", int
        ),
        mlp_hidden_units=_numeric_tuple(hyper["mlp_hidden_units"], "mlp_hidden_units", int),
        mlp_alpha=_numeric_tuple(hyper["mlp_alpha"], "mlp_alpha", float),
        final_model_selection_allowed=False,
        use_evaluation_for_selection=False,
    )


def split_for_day(day_index: int, split: SplitDays) -> SplitName:
    if not 0 <= day_index < split.total:
        raise SimpleModelError("day_index is outside the configured chronological split")
    if day_index < split.train:
        return "train"
    if day_index < split.train + split.validation:
        return "validation"
    if day_index < split.train + split.validation + split.calibration:
        return "calibration"
    return "engineering_holdout"


def _stable_rng(seed: int, row_id: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{row_id}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def generate_engineering_training_rows(config: SimpleModelConfig) -> list[TrainingRow]:
    if config.mode != "engineering_fixture":
        raise SimpleModelError("synthetic generator may be used only in engineering_fixture mode")
    rows: list[TrainingRow] = []
    for day in range(config.total_days):
        for symbol_index, symbol in enumerate(config.symbols):
            for side_index, side in enumerate(("bid", "ask")):
                for decision_index in range(config.rows_per_symbol_side_day):
                    row_id = f"{symbol}:{day:03d}:{side}:{decision_index:02d}"
                    rng = _stable_rng(config.random_seed, row_id)
                    spread = 1 + rng.randrange(5)
                    same_top1 = 35 + rng.randrange(190)
                    opposite_top1 = 35 + rng.randrange(190)
                    same_top5 = same_top1 + 100 + rng.randrange(620)
                    opposite_top5 = opposite_top1 + 100 + rng.randrange(620)
                    imbalance1 = math.trunc(
                        10000 * (same_top1 - opposite_top1) / (same_top1 + opposite_top1)
                    )
                    imbalance5 = math.trunc(
                        10000 * (same_top5 - opposite_top5) / (same_top5 + opposite_top5)
                    )
                    flow250 = rng.randrange(-90, 91)
                    flow1 = flow250 + rng.randrange(-140, 141)
                    flow5 = flow1 + rng.randrange(-260, 261)
                    count1 = rng.randrange(0, 18)
                    count5 = count1 + rng.randrange(0, 45)
                    mid250 = rng.randrange(-4, 5)
                    mid1 = mid250 + rng.randrange(-8, 9)
                    mid5 = mid1 + rng.randrange(-18, 19)
                    abs1 = abs(mid250) + abs(rng.randrange(-5, 6))
                    abs5 = abs1 + abs(rng.randrange(-20, 21))
                    spread_change = rng.randrange(-2, 3)
                    quote_age = rng.randrange(10_000_000, 4_900_000_001)
                    trade_age = rng.randrange(1_000_000, 5_100_000_001)
                    feature = {
                        "spread_ticks": spread,
                        "same_top1_lots": same_top1,
                        "opposite_top1_lots": opposite_top1,
                        "same_top5_lots": same_top5,
                        "opposite_top5_lots": opposite_top5,
                        "side_imbalance_top1_bps": imbalance1,
                        "side_imbalance_top5_bps": imbalance5,
                        "toward_quote_trade_flow_250ms_lots": flow250,
                        "toward_quote_trade_flow_1s_lots": flow1,
                        "toward_quote_trade_flow_5s_lots": flow5,
                        "trade_count_1s": count1,
                        "trade_count_5s": count5,
                        "side_mid_move_250ms_half_ticks": mid250,
                        "side_mid_move_1s_half_ticks": mid1,
                        "side_mid_move_5s_half_ticks": mid5,
                        "realized_abs_mid_move_1s_half_ticks": abs1,
                        "realized_abs_mid_move_5s_half_ticks": abs5,
                        "spread_change_1s_ticks": spread_change,
                        "quote_age_ns": quote_age,
                        "time_since_last_trade_ns": trade_age,
                    }
                    if tuple(feature) != FEATURE_NAMES:
                        raise SimpleModelError(
                            "synthetic row feature ordering drifted from Step 21"
                        )
                    # Synthetic hazard deliberately has linear and nonlinear components so all
                    # required model families exercise meaningful but non-research behavior.
                    temporal_shift = 0.22 if 70 <= day < 80 else (0.10 if day >= 80 else 0.0)
                    symbol_shift = 0.10 if symbol_index else -0.04
                    side_shift = 0.08 if side_index else -0.03
                    score = (
                        0.15
                        + 0.35 * (spread - 3)
                        - 0.0045 * (same_top1 - 120)
                        + 0.0025 * (opposite_top1 - 120)
                        - 0.00010 * imbalance1
                        + 0.0040 * flow250
                        + 0.0015 * flow1
                        + 0.055 * mid250
                        + 0.025 * abs1
                        + 0.40 * int(spread >= 4 and same_top1 < 90)
                        + temporal_shift
                        + symbol_shift
                        + side_shift
                    )
                    p5 = min(0.93, max(0.12, _sigmoid(score)))
                    u = max(1e-12, min(1.0 - 1e-12, rng.random()))
                    rate = -math.log1p(-p5) / 5.0
                    depletion_seconds = -math.log1p(-u) / rate
                    # Split-boundary diagnostic sentinels guarantee both classes are
                    # exercised for every instrument/horizon in the engineering fixture.
                    split_starts = {
                        0,
                        config.split_days.train,
                        config.split_days.train + config.split_days.validation,
                        config.split_days.train
                        + config.split_days.validation
                        + config.split_days.calibration,
                    }
                    if day in split_starts and decision_index == 0:
                        depletion_seconds = 0.10 if side == "bid" else 10.0
                    labels = {
                        "quote_depletion_250ms": int(depletion_seconds <= 0.250),
                        "quote_depletion_1s": int(depletion_seconds <= 1.0),
                        "quote_depletion_5s": int(depletion_seconds <= 5.0),
                    }
                    rows.append(
                        TrainingRow(
                            row_id=row_id,
                            symbol=symbol,
                            passive_side=side,
                            day_index=day,
                            decision_index=decision_index,
                            feature=feature,
                            labels=labels,
                        )
                    )
    validate_training_rows(rows, config)
    return rows


def validate_training_rows(rows: Iterable[TrainingRow], config: SimpleModelConfig) -> None:
    items = list(rows)
    expected = config.total_days * len(config.symbols) * 2 * config.rows_per_symbol_side_day
    if len(items) != expected:
        raise SimpleModelError(
            f"training fixture row count changed: expected {expected}, got {len(items)}"
        )
    seen: set[str] = set()
    previous_key: tuple[int, int, int, int] | None = None
    for row in items:
        if row.row_id in seen:
            raise SimpleModelError("duplicate training row_id")
        seen.add(row.row_id)
        if row.symbol not in config.symbols or row.passive_side not in {"bid", "ask"}:
            raise SimpleModelError("training row symbol/side is invalid")
        if tuple(row.feature) != config.feature_names:
            raise SimpleModelError("training row feature columns differ from Step 21")
        if any(not isinstance(value, int) for value in row.feature.values()):
            raise SimpleModelError("Step 22 fixture features must remain raw integer values")
        if set(row.labels) != set(HORIZON_TARGETS.values()) or any(
            value not in {0, 1} for value in row.labels.values()
        ):
            raise SimpleModelError("training labels are malformed")
        if not (
            row.labels["quote_depletion_250ms"]
            <= row.labels["quote_depletion_1s"]
            <= row.labels["quote_depletion_5s"]
        ):
            raise SimpleModelError("quote-depletion targets must be nested by horizon")
        key = (
            row.day_index,
            config.symbols.index(row.symbol),
            0 if row.passive_side == "bid" else 1,
            row.decision_index,
        )
        if previous_key is not None and key <= previous_key:
            raise SimpleModelError("training rows must be strictly chronological/canonical")
        previous_key = key
        split_for_day(row.day_index, config.split_days)
    # Every split/instrument/horizon must exercise both classes for engineering validity.
    for split_name in ("train", "validation", "calibration", "engineering_holdout"):
        for symbol in config.symbols:
            subset = [
                row
                for row in items
                if split_for_day(row.day_index, config.split_days) == split_name
                and row.symbol == symbol
            ]
            for horizon, target in HORIZON_TARGETS.items():
                classes = {row.labels[target] for row in subset}
                if classes != {0, 1}:
                    raise SimpleModelError(
                        f"{split_name}/{symbol}/{horizon} lacks both target classes"
                    )


def _matrix(
    rows: list[TrainingRow], config: SimpleModelConfig, horizon: str
) -> tuple[np.ndarray, np.ndarray]:
    if horizon not in HORIZON_TARGETS:
        raise SimpleModelError("unknown prediction horizon")
    x = np.asarray(
        [[row.feature[name] for name in config.feature_names] for row in rows],
        dtype=np.float64,
    )
    y = np.asarray([row.labels[HORIZON_TARGETS[horizon]] for row in rows], dtype=np.int64)
    if not np.isfinite(x).all():
        raise SimpleModelError("non-finite training feature")
    return x, y


def _rows_for_split(
    rows: list[TrainingRow], config: SimpleModelConfig, split_name: SplitName
) -> list[TrainingRow]:
    return [row for row in rows if split_for_day(row.day_index, config.split_days) == split_name]


def _fit_estimator(
    family: ModelFamily,
    params: dict[str, object],
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    seed: int,
    *,
    scaler_fit_x: np.ndarray | None = None,
) -> object:
    if family == "logistic":
        scaler_source = x_fit if scaler_fit_x is None else scaler_fit_x
        scaler = StandardScaler().fit(scaler_source)
        classifier = LogisticRegression(
            C=float(params["C"]), solver="lbfgs", max_iter=1000, random_state=seed
        )
        _fit_single_worker(classifier, scaler.transform(x_fit), y_fit)
        return TrainOnlyScaledEstimator(scaler=scaler, classifier=classifier)
    if family == "gradient_boosted_trees":
        estimator = HistGradientBoostingClassifier(
            learning_rate=float(params["learning_rate"]),
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            max_iter=100,
            l2_regularization=1e-3,
            early_stopping=False,
            random_state=seed,
        )
        _fit_single_worker(estimator, x_fit, y_fit)
        return estimator
    if family == "simple_mlp":
        scaler_source = x_fit if scaler_fit_x is None else scaler_fit_x
        scaler = StandardScaler().fit(scaler_source)
        classifier = MLPClassifier(
            hidden_layer_sizes=(int(params["hidden_units"]),),
            alpha=float(params["alpha"]),
            solver="lbfgs",
            max_iter=2000,
            random_state=seed,
        )
        _fit_single_worker(classifier, scaler.transform(x_fit), y_fit)
        return TrainOnlyScaledEstimator(scaler=scaler, classifier=classifier)
    raise SimpleModelError(f"cannot fit estimator for family {family}")


def _grid(config: SimpleModelConfig, family: ModelFamily) -> list[dict[str, object]]:
    if family == "base_rate":
        return [{}]
    if family == "logistic":
        return [{"C": value} for value in config.logistic_c]
    if family == "gradient_boosted_trees":
        return [
            {"learning_rate": lr, "max_leaf_nodes": leaves}
            for lr in config.boosted_learning_rate
            for leaves in config.boosted_max_leaf_nodes
        ]
    if family == "simple_mlp":
        return [
            {"hidden_units": hidden, "alpha": alpha}
            for hidden in config.mlp_hidden_units
            for alpha in config.mlp_alpha
        ]
    raise SimpleModelError("unsupported model family")


def _clip_probabilities(probabilities: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probabilities, dtype=np.float64), 1e-9, 1.0 - 1e-9)


def _log_loss(y: np.ndarray, probabilities: np.ndarray) -> float:
    return float(log_loss(y, _clip_probabilities(probabilities), labels=[0, 1]))


def _brier(y: np.ndarray, probabilities: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=np.float64)
    return float(np.mean((p - y) ** 2))


def _fit_platt(probabilities: np.ndarray, y: np.ndarray) -> PlattCalibrator:
    if {int(value) for value in y} != {0, 1}:
        raise SimpleModelError("calibration segment must contain both classes")
    p = _clip_probabilities(probabilities)
    z = np.log(p / (1.0 - p)).reshape(-1, 1)
    model = LogisticRegression(C=1e12, solver="lbfgs", max_iter=1000)
    _fit_single_worker(model, z, y)
    return PlattCalibrator(intercept=float(model.intercept_[0]), slope=float(model.coef_[0, 0]))


def _ece(y: np.ndarray, probabilities: np.ndarray, bins: int) -> float:
    total = len(y)
    if total == 0:
        raise SimpleModelError("cannot compute ECE on an empty sample")
    p = np.asarray(probabilities, dtype=np.float64)
    result = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        mask = (p >= low) & (p < high if index + 1 < bins else p <= high)
        count = int(mask.sum())
        if not count:
            continue
        result += count / total * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return result


def _calibration_regression(
    y: np.ndarray, probabilities: np.ndarray
) -> tuple[float | None, float | None]:
    if {int(value) for value in y} != {0, 1}:
        return None, None
    clipped = _clip_probabilities(probabilities)
    z = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    if float(np.std(z)) < 1e-12:
        return None, None
    model = LogisticRegression(C=1e12, solver="lbfgs", max_iter=1000)
    _fit_single_worker(model, z, y)
    return float(model.intercept_[0]), float(model.coef_[0, 0])


def probability_metrics(
    y: np.ndarray, probabilities: np.ndarray, config: SimpleModelConfig
) -> ProbabilityMetrics:
    if len(y) == 0:
        raise SimpleModelError("cannot compute probability metrics on an empty sample")
    p = _clip_probabilities(probabilities)
    intercept, slope = _calibration_regression(y, p)
    threshold_metrics: dict[str, dict[str, float]] = {}
    for threshold in config.precision_recall_thresholds:
        predicted = p >= threshold
        tp = int(np.sum(predicted & (y == 1)))
        fp = int(np.sum(predicted & (y == 0)))
        fn = int(np.sum((~predicted) & (y == 1)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        threshold_metrics[f"{threshold:.2f}"] = {"precision": precision, "recall": recall}
    classes = {int(value) for value in y}
    return ProbabilityMetrics(
        rows=len(y),
        positives=int(y.sum()),
        prevalence=float(y.mean()),
        log_loss=_log_loss(y, p),
        brier=_brier(y, p),
        ece=_ece(y, p, config.ece_bins),
        roc_auc=float(roc_auc_score(y, p)) if classes == {0, 1} else None,
        pr_auc=float(average_precision_score(y, p)) if classes == {0, 1} else None,
        calibration_intercept=intercept,
        calibration_slope=slope,
        threshold_metrics=threshold_metrics,
    )


def _prediction_for_estimator(estimator: object, x: np.ndarray) -> np.ndarray:
    return np.asarray(
        estimator.predict_proba(x)[:, 1],  # type: ignore[union-attr]
        dtype=np.float64,
    )


def select_hyperparameters(
    family: ModelFamily,
    horizon: str,
    train_rows: list[TrainingRow],
    validation_rows: list[TrainingRow],
    config: SimpleModelConfig,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    x_train, y_train = _matrix(train_rows, config, horizon)
    x_validation, y_validation = _matrix(validation_rows, config, horizon)
    candidates: list[dict[str, object]] = []
    if family == "base_rate":
        p = float(y_train.mean())
        probabilities = np.full(len(y_validation), p, dtype=np.float64)
        candidates.append(
            {
                "hyperparameters": {},
                "validation_log_loss": _log_loss(y_validation, probabilities),
                "validation_brier": _brier(y_validation, probabilities),
            }
        )
        return {}, candidates
    for params in _grid(config, family):
        estimator = _fit_estimator(family, params, x_train, y_train, config.random_seed)
        probabilities = _prediction_for_estimator(estimator, x_validation)
        candidates.append(
            {
                "hyperparameters": params,
                "validation_log_loss": _log_loss(y_validation, probabilities),
                "validation_brier": _brier(y_validation, probabilities),
            }
        )
    candidates.sort(
        key=lambda item: (
            float(item["validation_log_loss"]),
            float(item["validation_brier"]),
            json.dumps(item["hyperparameters"], sort_keys=True),
        )
    )
    return dict(candidates[0]["hyperparameters"]), candidates


def fit_selected_model(
    family: ModelFamily,
    horizon: str,
    selected_params: dict[str, object],
    train_rows: list[TrainingRow],
    validation_rows: list[TrainingRow],
    calibration_rows: list[TrainingRow],
    config: SimpleModelConfig,
) -> FittedSimpleModel:
    development_rows = train_rows + validation_rows
    x_train, y_train = _matrix(train_rows, config, horizon)
    x_development, y_development = _matrix(development_rows, config, horizon)
    x_calibration, y_calibration = _matrix(calibration_rows, config, horizon)
    prevalence = float(y_train.mean())
    if family == "base_rate":
        return FittedSimpleModel(
            family=family,
            horizon=horizon,
            hyperparameters={},
            estimator=None,
            constant_probability=prevalence,
            calibrator=None,
            train_prevalence=prevalence,
            feature_names=config.feature_names,
        )
    estimator = _fit_estimator(
        family,
        selected_params,
        x_development,
        y_development,
        config.random_seed,
        scaler_fit_x=x_train if family in {"logistic", "simple_mlp"} else None,
    )
    uncalibrated = _prediction_for_estimator(estimator, x_calibration)
    calibrator = _fit_platt(uncalibrated, y_calibration)
    return FittedSimpleModel(
        family=family,
        horizon=horizon,
        hyperparameters=selected_params,
        estimator=estimator,
        constant_probability=None,
        calibrator=calibrator,
        train_prevalence=prevalence,
        feature_names=config.feature_names,
    )


def model_card(
    model: FittedSimpleModel,
    config: SimpleModelConfig,
    validation_candidates: list[dict[str, object]],
) -> dict[str, object]:
    estimator_name = None if model.estimator is None else type(model.estimator).__name__
    scaler_fitted_on = (
        "train_only" if model.family in {"logistic", "simple_mlp"} else "not_applicable"
    )
    return {
        "schema_version": "simple-model-card-v1",
        "step": 22,
        "family": model.family,
        "horizon": model.horizon,
        "feature_names": list(model.feature_names),
        "hyperparameters": model.hyperparameters,
        "hyperparameter_selection_segment": "validation",
        "validation_candidates": validation_candidates,
        "final_fit_segment": "train_plus_validation",
        "calibration_segment": "calibration" if model.calibrator else "none_base_rate",
        "calibration_method": config.calibration_method if model.calibrator else "none",
        "calibration": None if model.calibrator is None else asdict(model.calibrator),
        "scaler_fitted_on": scaler_fitted_on,
        "estimator_class": estimator_name,
        "training_prevalence": model.train_prevalence,
        "research_status": "synthetic_validation_only_non_research",
        "selected_as_final_model": False,
        "selected_as_primary_horizon": False,
        "locked_test_used_for_selection": False,
    }


def prediction_rows(
    model: FittedSimpleModel,
    rows: list[TrainingRow],
    config: SimpleModelConfig,
    split_name: SplitName,
) -> tuple[list[dict[str, object]], ProbabilityMetrics, ProbabilityMetrics]:
    x, y = _matrix(rows, config, model.horizon)
    raw = model.predict_uncalibrated(x)
    calibrated = model.predict_calibrated(x)
    result = [
        {
            "row_id": row.row_id,
            "symbol": row.symbol,
            "passive_side": row.passive_side,
            "day_index": row.day_index,
            "split": split_name,
            "horizon": model.horizon,
            "family": model.family,
            "target": int(target),
            "uncalibrated_probability": float(p_raw),
            "calibrated_probability": float(p_cal),
        }
        for row, target, p_raw, p_cal in zip(rows, y, raw, calibrated, strict=True)
    ]
    return result, probability_metrics(y, raw, config), probability_metrics(y, calibrated, config)


def slice_metrics(
    model: FittedSimpleModel,
    rows: list[TrainingRow],
    config: SimpleModelConfig,
) -> dict[str, dict[str, object]]:
    slices: dict[str, list[TrainingRow]] = {}
    for symbol in config.symbols:
        slices[f"instrument:{symbol}"] = [row for row in rows if row.symbol == symbol]
    for side in ("bid", "ask"):
        slices[f"side:{side}"] = [row for row in rows if row.passive_side == side]
    start = config.split_days.train + config.split_days.validation + config.split_days.calibration
    midpoint = start + config.split_days.engineering_holdout // 2
    slices["temporal:first_half"] = [row for row in rows if start <= row.day_index < midpoint]
    slices["temporal:second_half"] = [
        row for row in rows if midpoint <= row.day_index < config.total_days
    ]
    output: dict[str, dict[str, object]] = {}
    for name, subset in slices.items():
        if not subset:
            continue
        x, y = _matrix(subset, config, model.horizon)
        calibrated = model.predict_calibrated(x)
        output[name] = asdict(probability_metrics(y, calibrated, config))
    return output


def serialize_model(model: FittedSimpleModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = pickle.dumps(model, protocol=5)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(payload)
    temporary.replace(path)


def load_serialized_model(path: Path) -> FittedSimpleModel:
    try:
        value = pickle.loads(path.read_bytes())
    except (OSError, pickle.UnpicklingError, EOFError) as exc:
        raise SimpleModelError(f"cannot load model artifact: {exc}") from exc
    if not isinstance(value, FittedSimpleModel):
        raise SimpleModelError("model artifact has the wrong type")
    return value


def benchmark_batch_one(
    model: FittedSimpleModel,
    rows: list[TrainingRow],
    config: SimpleModelConfig,
    repetitions: int = 200,
) -> dict[str, object]:
    if repetitions < 10:
        raise SimpleModelError("inference benchmark requires at least 10 repetitions")
    x, _ = _matrix(rows[:1], config, model.horizon)
    # Warm-up is excluded from measurements.
    for _ in range(20):
        model.predict_calibrated(x)
    timings: list[int] = []
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        model.predict_calibrated(x)
        timings.append(time.perf_counter_ns() - started)
    timings.sort()
    return {
        "repetitions": repetitions,
        "p50_ns": timings[len(timings) // 2],
        "p95_ns": timings[min(len(timings) - 1, math.ceil(0.95 * len(timings)) - 1)],
        "p99_ns": timings[min(len(timings) - 1, math.ceil(0.99 * len(timings)) - 1)],
        "mean_ns": statistics.fmean(timings),
        "claim_status": "engineering_machine_specific_not_step30_performance_claim",
    }


def canonical_config_sha256(config: SimpleModelConfig) -> str:
    raw = asdict(config)
    return hashlib.sha256(canonical_json_bytes(raw)).hexdigest()


def reliability_bins(
    y: np.ndarray, probabilities: np.ndarray, bins: int
) -> list[dict[str, object]]:
    if bins < 2:
        raise SimpleModelError("reliability diagram requires at least two bins")
    p = np.asarray(probabilities, dtype=np.float64)
    output: list[dict[str, object]] = []
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        mask = (p >= low) & (p < high if index + 1 < bins else p <= high)
        count = int(mask.sum())
        output.append(
            {
                "bin": index,
                "lower": low,
                "upper": high,
                "count": count,
                "mean_probability": None if not count else float(p[mask].mean()),
                "observed_frequency": None if not count else float(y[mask].mean()),
            }
        )
    return output
