"""Step 23 compact causal temporal deep model.

The committed fixture is an engineering validation only. It mirrors the frozen
chronological split and Step 21 feature contract without selecting a research
horizon, final model family, or opening the locked historical test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Iterable, Literal

import numpy as np
from sklearn.linear_model import LogisticRegression

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.prediction.artifacts import FEATURE_NAMES
from robust_execution.prediction.simple_models import (
    HORIZON_TARGETS,
    PlattCalibrator,
    ProbabilityMetrics,
    SimpleModelConfig,
    SplitDays,
    TrainingRow,
    generate_engineering_training_rows,
    probability_metrics,
    reliability_bins,
    split_for_day,
)

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - exercised by optional-dependency smoke test
    raise ImportError(
        "Step 23 temporal models require the optional deep-models dependency group"
    ) from exc

SplitName = Literal["train", "validation", "calibration", "engineering_holdout"]


class TemporalModelError(RuntimeError):
    """Raised when Step 23 would violate the temporal-model protocol."""


@dataclass(frozen=True)
class TemporalHyperparameters:
    conv_channels: int
    lstm_hidden_units: int
    learning_rate: float
    weight_decay: float
    max_epochs: int
    patience: int


@dataclass(frozen=True)
class DecisionProxyConfig:
    aggressive_cost: float
    passive_depletion_cost: float


@dataclass(frozen=True)
class OODStressConfig:
    spread_add_ticks: int
    same_depth_scale: float
    opposite_depth_scale: float
    quote_age_scale: float
    trade_age_scale: float


@dataclass(frozen=True)
class TemporalModelConfig:
    schema_version: str
    dataset_id: str
    symbols: tuple[str, ...]
    feature_names: tuple[str, ...]
    candidate_horizons: tuple[str, ...]
    selected_horizon: str
    mode: Literal["engineering_fixture", "research"]
    split_days: SplitDays
    rows_per_symbol_side_day: int
    sequence_length: int
    sequence_stride: int
    random_seed: int
    calibration_method: str
    ece_bins: int
    precision_recall_thresholds: tuple[float, ...]
    architecture: str
    conv_kernel_size: int
    hyperparameters: tuple[TemporalHyperparameters, ...]
    batch_size: int
    decision_proxy: DecisionProxyConfig
    ood_feature_stress: OODStressConfig
    final_model_selection_allowed: bool
    use_engineering_holdout_for_selection: bool
    use_decision_proxy_for_selection: bool

    @property
    def total_days(self) -> int:
        return self.split_days.total


@dataclass(frozen=True)
class TemporalSequence:
    sequence_id: str
    symbol: str
    passive_side: Literal["bid", "ask"]
    day_index: int
    start_decision_index: int
    end_decision_index: int
    rows: tuple[TrainingRow, ...]

    @property
    def endpoint(self) -> TrainingRow:
        return self.rows[-1]


@dataclass(frozen=True)
class FeatureScaler:
    mean: tuple[float, ...]
    scale: tuple[float, ...]

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        mean = np.asarray(self.mean, dtype=np.float32)
        scale = np.asarray(self.scale, dtype=np.float32)
        return (np.asarray(matrix, dtype=np.float32) - mean) / scale


@dataclass(frozen=True)
class CandidateResult:
    hyperparameters: TemporalHyperparameters
    best_epoch: int
    validation_log_loss: float
    validation_brier: float
    parameter_count: int


@dataclass
class FittedTemporalModel:
    horizon: str
    hyperparameters: TemporalHyperparameters
    best_epoch: int
    scaler: FeatureScaler
    calibrator: PlattCalibrator
    train_prevalence: float
    feature_names: tuple[str, ...]
    sequence_length: int
    conv_kernel_size: int
    network: nn.Module

    def predict_uncalibrated(self, matrix: np.ndarray) -> np.ndarray:
        x = self.scaler.transform(matrix)
        tensor = torch.from_numpy(x)
        self.network.eval()
        with torch.inference_mode():
            logits = self.network(tensor).detach().cpu().numpy().reshape(-1)
        logits = np.clip(logits.astype(np.float64), -40.0, 40.0)
        return 1.0 / (1.0 + np.exp(-logits))

    def predict_calibrated(self, matrix: np.ndarray) -> np.ndarray:
        return self.calibrator.predict(self.predict_uncalibrated(matrix))


class CausalConvLSTM(nn.Module):
    """Small causal Conv1D -> LSTM classifier for engineered feature sequences."""

    def __init__(
        self,
        feature_count: int,
        conv_channels: int,
        lstm_hidden_units: int,
        kernel_size: int,
    ) -> None:
        super().__init__()
        self.kernel_size = kernel_size
        self.conv = nn.Conv1d(feature_count, conv_channels, kernel_size=kernel_size)
        self.activation = nn.GELU()
        self.lstm = nn.LSTM(conv_channels, lstm_hidden_units, batch_first=True)
        self.head = nn.Linear(lstm_hidden_units, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [batch, time, feature]. Left padding only makes the convolution causal.
        transposed = x.transpose(1, 2)
        padded = torch.nn.functional.pad(transposed, (self.kernel_size - 1, 0))
        local = self.activation(self.conv(padded)).transpose(1, 2)
        recurrent, _ = self.lstm(local)
        return self.head(recurrent[:, -1, :]).squeeze(-1)


def _strict_keys(raw: dict[str, Any], expected: set[str], context: str) -> None:
    if set(raw) != expected:
        raise TemporalModelError(
            f"{context} keys differ; missing={sorted(expected-set(raw))}, "
            f"extra={sorted(set(raw)-expected)}"
        )


def _positive_int(value: object, name: str, minimum: int = 1) -> int:
    if not isinstance(value, int) or value < minimum:
        raise TemporalModelError(f"{name} must be an integer >= {minimum}")
    return value


def _positive_float(value: object, name: str, allow_zero: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TemporalModelError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0.0 or (result == 0.0 and not allow_zero):
        raise TemporalModelError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return result


def load_temporal_model_config(path: Path) -> TemporalModelConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemporalModelError(f"cannot read Step 23 config: {exc}") from exc
    if not isinstance(raw, dict):
        raise TemporalModelError("Step 23 config must be a JSON object")
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
        "sequence_length",
        "sequence_stride",
        "random_seed",
        "calibration_method",
        "ece_bins",
        "precision_recall_thresholds",
        "architecture",
        "conv_kernel_size",
        "hyperparameters",
        "batch_size",
        "decision_proxy",
        "ood_feature_stress",
        "final_model_selection_allowed",
        "use_engineering_holdout_for_selection",
        "use_decision_proxy_for_selection",
    }
    _strict_keys(raw, expected, "Step 23 config")
    if raw["schema_version"] != "temporal-deep-training-config-v1":
        raise TemporalModelError("unsupported Step 23 config schema")
    symbols = raw["symbols"]
    features = raw["feature_names"]
    horizons = raw["candidate_horizons"]
    if not isinstance(symbols, list) or tuple(symbols) != ("BTCUSDT", "ETHUSDT"):
        raise TemporalModelError("Step 23 symbols must remain BTCUSDT and ETHUSDT")
    if not isinstance(features, list) or tuple(features) != FEATURE_NAMES:
        raise TemporalModelError("Step 23 must use the exact frozen Step 21 feature ordering")
    if not isinstance(horizons, list) or tuple(horizons) != ("250ms", "1s", "5s"):
        raise TemporalModelError("Step 23 candidate horizons must remain 250ms, 1s and 5s")
    mode = raw["mode"]
    selected = str(raw["selected_horizon"])
    if mode not in {"engineering_fixture", "research"}:
        raise TemporalModelError("mode must be engineering_fixture or research")
    if mode == "engineering_fixture" and selected != "PRE_DATA_FIELD_BEFORE_CALIBRATION":
        raise TemporalModelError("engineering fixture may not freeze the research horizon")
    if mode == "research" and selected not in horizons:
        raise TemporalModelError("research mode requires a previously frozen candidate horizon")
    for key in (
        "final_model_selection_allowed",
        "use_engineering_holdout_for_selection",
        "use_decision_proxy_for_selection",
    ):
        if raw[key] is not False:
            raise TemporalModelError(f"{key} must remain false at Step 23")
    split_raw = raw["split_days"]
    if not isinstance(split_raw, dict):
        raise TemporalModelError("split_days must be an object")
    _strict_keys(
        split_raw,
        {"train", "validation", "calibration", "engineering_holdout"},
        "split_days",
    )
    split = SplitDays(
        *(
            int(split_raw[key])
            for key in ("train", "validation", "calibration", "engineering_holdout")
        )
    )
    if (split.train, split.validation, split.calibration, split.engineering_holdout) != (
        50,
        20,
        10,
        20,
    ):
        raise TemporalModelError("Step 23 engineering split must mirror 50/20/10/20 whole days")
    rows_per = _positive_int(raw["rows_per_symbol_side_day"], "rows_per_symbol_side_day")
    sequence_length = _positive_int(raw["sequence_length"], "sequence_length", 2)
    stride = _positive_int(raw["sequence_stride"], "sequence_stride")
    if sequence_length > rows_per:
        raise TemporalModelError("sequence_length cannot exceed rows_per_symbol_side_day")
    if raw["architecture"] != "causal_conv1d_lstm":
        raise TemporalModelError("Step 23 architecture must remain causal_conv1d_lstm")
    kernel = _positive_int(raw["conv_kernel_size"], "conv_kernel_size", 2)
    if kernel > sequence_length:
        raise TemporalModelError("conv_kernel_size cannot exceed sequence_length")
    if raw["calibration_method"] != "platt_logit":
        raise TemporalModelError("Step 23 calibration method must remain platt_logit")
    seed = raw["random_seed"]
    if not isinstance(seed, int) or seed < 0:
        raise TemporalModelError("random_seed must be a non-negative integer")
    ece_bins = _positive_int(raw["ece_bins"], "ece_bins", 2)
    thresholds_raw = raw["precision_recall_thresholds"]
    if not isinstance(thresholds_raw, list) or not thresholds_raw:
        raise TemporalModelError("precision_recall_thresholds must be non-empty")
    thresholds = tuple(float(value) for value in thresholds_raw)
    if (
        any(not 0.0 < value < 1.0 for value in thresholds)
        or tuple(sorted(set(thresholds))) != thresholds
    ):
        raise TemporalModelError("thresholds must be unique, increasing, and inside (0,1)")
    hyper_raw = raw["hyperparameters"]
    if not isinstance(hyper_raw, list) or not 1 <= len(hyper_raw) <= 8:
        raise TemporalModelError("hyperparameters must contain one to eight candidates")
    candidates: list[TemporalHyperparameters] = []
    for index, item in enumerate(hyper_raw):
        if not isinstance(item, dict):
            raise TemporalModelError("hyperparameter candidates must be objects")
        _strict_keys(
            item,
            {
                "conv_channels",
                "lstm_hidden_units",
                "learning_rate",
                "weight_decay",
                "max_epochs",
                "patience",
            },
            f"hyperparameters[{index}]",
        )
        candidate = TemporalHyperparameters(
            conv_channels=_positive_int(item["conv_channels"], "conv_channels"),
            lstm_hidden_units=_positive_int(item["lstm_hidden_units"], "lstm_hidden_units"),
            learning_rate=_positive_float(item["learning_rate"], "learning_rate"),
            weight_decay=_positive_float(item["weight_decay"], "weight_decay", allow_zero=True),
            max_epochs=_positive_int(item["max_epochs"], "max_epochs", 2),
            patience=_positive_int(item["patience"], "patience"),
        )
        if candidate.patience >= candidate.max_epochs:
            raise TemporalModelError("patience must be less than max_epochs")
        candidates.append(candidate)
    proxy_raw = raw["decision_proxy"]
    if not isinstance(proxy_raw, dict):
        raise TemporalModelError("decision_proxy must be an object")
    _strict_keys(proxy_raw, {"aggressive_cost", "passive_depletion_cost"}, "decision_proxy")
    proxy = DecisionProxyConfig(
        aggressive_cost=_positive_float(proxy_raw["aggressive_cost"], "aggressive_cost"),
        passive_depletion_cost=_positive_float(
            proxy_raw["passive_depletion_cost"], "passive_depletion_cost"
        ),
    )
    if proxy.aggressive_cost >= proxy.passive_depletion_cost:
        raise TemporalModelError("aggressive_cost must be below passive_depletion_cost")
    ood_raw = raw["ood_feature_stress"]
    if not isinstance(ood_raw, dict):
        raise TemporalModelError("ood_feature_stress must be an object")
    _strict_keys(
        ood_raw,
        {
            "spread_add_ticks",
            "same_depth_scale",
            "opposite_depth_scale",
            "quote_age_scale",
            "trade_age_scale",
        },
        "ood_feature_stress",
    )
    ood = OODStressConfig(
        spread_add_ticks=_positive_int(ood_raw["spread_add_ticks"], "spread_add_ticks"),
        same_depth_scale=_positive_float(ood_raw["same_depth_scale"], "same_depth_scale"),
        opposite_depth_scale=_positive_float(
            ood_raw["opposite_depth_scale"], "opposite_depth_scale"
        ),
        quote_age_scale=_positive_float(ood_raw["quote_age_scale"], "quote_age_scale"),
        trade_age_scale=_positive_float(ood_raw["trade_age_scale"], "trade_age_scale"),
    )
    return TemporalModelConfig(
        schema_version=str(raw["schema_version"]),
        dataset_id=str(raw["dataset_id"]),
        symbols=tuple(symbols),
        feature_names=tuple(features),
        candidate_horizons=tuple(horizons),
        selected_horizon=selected,
        mode=mode,
        split_days=split,
        rows_per_symbol_side_day=rows_per,
        sequence_length=sequence_length,
        sequence_stride=stride,
        random_seed=seed,
        calibration_method=str(raw["calibration_method"]),
        ece_bins=ece_bins,
        precision_recall_thresholds=thresholds,
        architecture=str(raw["architecture"]),
        conv_kernel_size=kernel,
        hyperparameters=tuple(candidates),
        batch_size=_positive_int(raw["batch_size"], "batch_size"),
        decision_proxy=proxy,
        ood_feature_stress=ood,
        final_model_selection_allowed=False,
        use_engineering_holdout_for_selection=False,
        use_decision_proxy_for_selection=False,
    )


def _simple_config(config: TemporalModelConfig) -> SimpleModelConfig:
    # Reuse the Step 22 deterministic engineering row generator while changing only
    # rows-per-day and the seed. This preserves the exact Step 21 raw feature contract.
    return SimpleModelConfig(
        schema_version="simple-model-training-config-v1",
        dataset_id=f"{config.dataset_id}-rows",
        symbols=config.symbols,
        feature_names=config.feature_names,
        candidate_horizons=config.candidate_horizons,
        selected_horizon=config.selected_horizon,
        mode=config.mode,
        split_days=config.split_days,
        rows_per_symbol_side_day=config.rows_per_symbol_side_day,
        random_seed=config.random_seed,
        calibration_method=config.calibration_method,
        ece_bins=config.ece_bins,
        precision_recall_thresholds=config.precision_recall_thresholds,
        logistic_c=(1.0,),
        boosted_learning_rate=(0.1,),
        boosted_max_leaf_nodes=(7,),
        mlp_hidden_units=(8,),
        mlp_alpha=(0.001,),
        final_model_selection_allowed=False,
        use_evaluation_for_selection=False,
    )


def generate_temporal_training_rows(config: TemporalModelConfig) -> list[TrainingRow]:
    return generate_engineering_training_rows(_simple_config(config))


def build_sequences(
    rows: Iterable[TrainingRow], config: TemporalModelConfig
) -> list[TemporalSequence]:
    groups: dict[tuple[int, str, str], list[TrainingRow]] = {}
    for row in rows:
        key = (row.day_index, row.symbol, row.passive_side)
        groups.setdefault(key, []).append(row)
    sequences: list[TemporalSequence] = []
    for (day, symbol, side), group in sorted(
        groups.items(),
        key=lambda item: (
            item[0][0],
            config.symbols.index(item[0][1]),
            0 if item[0][2] == "bid" else 1,
        ),
    ):
        ordered = sorted(group, key=lambda row: row.decision_index)
        expected_indices = list(range(config.rows_per_symbol_side_day))
        if [row.decision_index for row in ordered] != expected_indices:
            raise TemporalModelError("temporal sequence source rows are incomplete or reordered")
        for start in range(
            0,
            len(ordered) - config.sequence_length + 1,
            config.sequence_stride,
        ):
            window = tuple(ordered[start : start + config.sequence_length])
            endpoint = window[-1]
            sequences.append(
                TemporalSequence(
                    sequence_id=(
                        f"{symbol}:{day:03d}:{side}:{start:02d}-{endpoint.decision_index:02d}"
                    ),
                    symbol=symbol,
                    passive_side=side,  # type: ignore[arg-type]
                    day_index=day,
                    start_decision_index=window[0].decision_index,
                    end_decision_index=endpoint.decision_index,
                    rows=window,
                )
            )
    validate_sequences(sequences, config)
    return sequences


def validate_sequences(sequences: Iterable[TemporalSequence], config: TemporalModelConfig) -> None:
    items = list(sequences)
    per_group = 1 + (
        config.rows_per_symbol_side_day - config.sequence_length
    ) // config.sequence_stride
    expected = config.total_days * len(config.symbols) * 2 * per_group
    if len(items) != expected:
        raise TemporalModelError(f"sequence count changed: expected {expected}, got {len(items)}")
    seen: set[str] = set()
    previous: tuple[int, int, int, int] | None = None
    for sequence in items:
        if sequence.sequence_id in seen:
            raise TemporalModelError("duplicate temporal sequence_id")
        seen.add(sequence.sequence_id)
        if len(sequence.rows) != config.sequence_length:
            raise TemporalModelError("sequence length changed")
        if any(row.day_index != sequence.day_index for row in sequence.rows):
            raise TemporalModelError("sequence crosses a day boundary")
        if any(row.symbol != sequence.symbol for row in sequence.rows):
            raise TemporalModelError("sequence crosses an instrument boundary")
        if any(row.passive_side != sequence.passive_side for row in sequence.rows):
            raise TemporalModelError("sequence crosses a passive-side boundary")
        indices = [row.decision_index for row in sequence.rows]
        if indices != list(range(indices[0], indices[0] + config.sequence_length)):
            raise TemporalModelError("sequence rows are not contiguous in decision time")
        if tuple(sequence.endpoint.feature) != config.feature_names:
            raise TemporalModelError("endpoint feature contract differs from Step 21")
        key = (
            sequence.day_index,
            config.symbols.index(sequence.symbol),
            0 if sequence.passive_side == "bid" else 1,
            sequence.start_decision_index,
        )
        if previous is not None and key <= previous:
            raise TemporalModelError("sequence ordering is not deterministic")
        previous = key
    for split_name in ("train", "validation", "calibration", "engineering_holdout"):
        subset = [
            item
            for item in items
            if split_for_day(item.day_index, config.split_days) == split_name
        ]
        if not subset:
            raise TemporalModelError(f"{split_name} sequence split is empty")
        for horizon in config.candidate_horizons:
            labels = {item.endpoint.labels[HORIZON_TARGETS[horizon]] for item in subset}
            if labels != {0, 1}:
                raise TemporalModelError(f"{split_name}/{horizon} does not contain both classes")


def split_sequences(
    sequences: Iterable[TemporalSequence], config: TemporalModelConfig
) -> dict[SplitName, list[TemporalSequence]]:
    output: dict[SplitName, list[TemporalSequence]] = {
        "train": [],
        "validation": [],
        "calibration": [],
        "engineering_holdout": [],
    }
    for sequence in sequences:
        output[split_for_day(sequence.day_index, config.split_days)].append(sequence)
    return output


def sequence_matrix(
    sequences: list[TemporalSequence], config: TemporalModelConfig, horizon: str
) -> tuple[np.ndarray, np.ndarray]:
    if horizon not in config.candidate_horizons:
        raise TemporalModelError(f"unsupported horizon {horizon}")
    x = np.asarray(
        [
            [[row.feature[name] for name in config.feature_names] for row in sequence.rows]
            for sequence in sequences
        ],
        dtype=np.float32,
    )
    y = np.asarray(
        [sequence.endpoint.labels[HORIZON_TARGETS[horizon]] for sequence in sequences],
        dtype=np.float32,
    )
    return x, y


def fit_feature_scaler(x_train: np.ndarray) -> FeatureScaler:
    if x_train.ndim != 3 or x_train.shape[0] == 0:
        raise TemporalModelError("training sequence tensor must be non-empty and three-dimensional")
    flat = np.asarray(x_train, dtype=np.float64).reshape(-1, x_train.shape[-1])
    mean = flat.mean(axis=0)
    scale = flat.std(axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    return FeatureScaler(
        mean=tuple(float(value) for value in mean),
        scale=tuple(float(value) for value in scale),
    )


def _set_deterministic(seed: int) -> None:
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.use_deterministic_algorithms(True)


def _candidate_seed(config: TemporalModelConfig, horizon: str, candidate: object) -> int:
    material = (
        f"{config.random_seed}|{horizon}|"
        f"{json.dumps(candidate, sort_keys=True, default=str)}"
    )
    return int.from_bytes(hashlib.sha256(material.encode()).digest()[:4], "big")


def _network(config: TemporalModelConfig, hyper: TemporalHyperparameters) -> CausalConvLSTM:
    return CausalConvLSTM(
        feature_count=len(config.feature_names),
        conv_channels=hyper.conv_channels,
        lstm_hidden_units=hyper.lstm_hidden_units,
        kernel_size=config.conv_kernel_size,
    )


def parameter_count(network: nn.Module) -> int:
    return sum(parameter.numel() for parameter in network.parameters())


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    clipped = np.clip(np.asarray(p, dtype=np.float64), 1e-9, 1.0 - 1e-9)
    target = np.asarray(y, dtype=np.float64)
    return float(-np.mean(target * np.log(clipped) + (1.0 - target) * np.log1p(-clipped)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(p, dtype=np.float64) - np.asarray(y, dtype=np.float64)) ** 2))


def _batch_indices(count: int, batch_size: int) -> Iterable[tuple[int, int]]:
    for start in range(0, count, batch_size):
        yield start, min(count, start + batch_size)


def _train_epochs(
    network: CausalConvLSTM,
    x: np.ndarray,
    y: np.ndarray,
    hyper: TemporalHyperparameters,
    batch_size: int,
    epochs: int,
) -> None:
    optimizer = torch.optim.AdamW(
        network.parameters(), lr=hyper.learning_rate, weight_decay=hyper.weight_decay
    )
    criterion = nn.BCEWithLogitsLoss()
    network.train()
    x_tensor = torch.from_numpy(np.asarray(x, dtype=np.float32))
    y_tensor = torch.from_numpy(np.asarray(y, dtype=np.float32))
    for _ in range(epochs):
        for start, stop in _batch_indices(len(x), batch_size):
            optimizer.zero_grad(set_to_none=True)
            logits = network(x_tensor[start:stop])
            loss = criterion(logits, y_tensor[start:stop])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(network.parameters(), max_norm=5.0)
            optimizer.step()


def _predict_network(network: nn.Module, x: np.ndarray) -> np.ndarray:
    network.eval()
    with torch.inference_mode():
        logits = network(torch.from_numpy(np.asarray(x, dtype=np.float32))).cpu().numpy()
    logits = np.clip(np.asarray(logits, dtype=np.float64).reshape(-1), -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-logits))


def select_temporal_hyperparameters(
    horizon: str,
    train_sequences: list[TemporalSequence],
    validation_sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> tuple[TemporalHyperparameters, int, list[CandidateResult]]:
    x_train_raw, y_train = sequence_matrix(train_sequences, config, horizon)
    x_validation_raw, y_validation = sequence_matrix(validation_sequences, config, horizon)
    scaler = fit_feature_scaler(x_train_raw)
    x_train = scaler.transform(x_train_raw)
    x_validation = scaler.transform(x_validation_raw)
    results: list[CandidateResult] = []
    for hyper in config.hyperparameters:
        seed = _candidate_seed(config, horizon, asdict(hyper))
        _set_deterministic(seed)
        network = _network(config, hyper)
        optimizer = torch.optim.AdamW(
            network.parameters(), lr=hyper.learning_rate, weight_decay=hyper.weight_decay
        )
        criterion = nn.BCEWithLogitsLoss()
        x_tensor = torch.from_numpy(x_train)
        y_tensor = torch.from_numpy(y_train)
        best_loss = math.inf
        best_brier = math.inf
        best_epoch = 0
        stale = 0
        for epoch in range(1, hyper.max_epochs + 1):
            network.train()
            for start, stop in _batch_indices(len(x_train), config.batch_size):
                optimizer.zero_grad(set_to_none=True)
                logits = network(x_tensor[start:stop])
                loss = criterion(logits, y_tensor[start:stop])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(network.parameters(), max_norm=5.0)
                optimizer.step()
            probabilities = _predict_network(network, x_validation)
            val_loss = _log_loss(y_validation, probabilities)
            val_brier = _brier(y_validation, probabilities)
            if (val_loss, val_brier, epoch) < (best_loss, best_brier, best_epoch or epoch + 1):
                best_loss = val_loss
                best_brier = val_brier
                best_epoch = epoch
                stale = 0
            else:
                stale += 1
                if stale >= hyper.patience:
                    break
        results.append(
            CandidateResult(
                hyperparameters=hyper,
                best_epoch=best_epoch,
                validation_log_loss=best_loss,
                validation_brier=best_brier,
                parameter_count=parameter_count(network),
            )
        )
    results.sort(
        key=lambda result: (
            result.validation_log_loss,
            result.validation_brier,
            json.dumps(asdict(result.hyperparameters), sort_keys=True),
        )
    )
    selected = results[0]
    return selected.hyperparameters, selected.best_epoch, results


def _fit_platt(probabilities: np.ndarray, y: np.ndarray) -> PlattCalibrator:
    classes = set(int(value) for value in y)
    if classes != {0, 1}:
        raise TemporalModelError("calibration segment must contain both classes")
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-9, 1.0 - 1e-9)
    z = np.log(p / (1.0 - p)).reshape(-1, 1)
    model = LogisticRegression(C=1e12, solver="lbfgs", max_iter=1000)
    model.fit(z, np.asarray(y, dtype=np.int64))
    return PlattCalibrator(intercept=float(model.intercept_[0]), slope=float(model.coef_[0, 0]))


def fit_selected_temporal_model(
    horizon: str,
    selected: TemporalHyperparameters,
    best_epoch: int,
    train_sequences: list[TemporalSequence],
    validation_sequences: list[TemporalSequence],
    calibration_sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> FittedTemporalModel:
    x_train_raw, y_train = sequence_matrix(train_sequences, config, horizon)
    scaler = fit_feature_scaler(x_train_raw)
    development = train_sequences + validation_sequences
    x_development_raw, y_development = sequence_matrix(development, config, horizon)
    x_calibration_raw, y_calibration = sequence_matrix(calibration_sequences, config, horizon)
    seed = _candidate_seed(config, horizon, {"final": asdict(selected), "epoch": best_epoch})
    _set_deterministic(seed)
    network = _network(config, selected)
    _train_epochs(
        network,
        scaler.transform(x_development_raw),
        y_development,
        selected,
        config.batch_size,
        best_epoch,
    )
    calibration_probability = _predict_network(network, scaler.transform(x_calibration_raw))
    calibrator = _fit_platt(calibration_probability, y_calibration)
    return FittedTemporalModel(
        horizon=horizon,
        hyperparameters=selected,
        best_epoch=best_epoch,
        scaler=scaler,
        calibrator=calibrator,
        train_prevalence=float(y_train.mean()),
        feature_names=config.feature_names,
        sequence_length=config.sequence_length,
        conv_kernel_size=config.conv_kernel_size,
        network=network,
    )


def metric_config(config: TemporalModelConfig) -> SimpleModelConfig:
    return _simple_config(config)


def prediction_rows(
    model: FittedTemporalModel,
    sequences: list[TemporalSequence],
    config: TemporalModelConfig,
    split_name: str,
) -> tuple[list[dict[str, object]], ProbabilityMetrics, ProbabilityMetrics]:
    x, y = sequence_matrix(sequences, config, model.horizon)
    raw = model.predict_uncalibrated(x)
    calibrated = model.predict_calibrated(x)
    rows = [
        {
            "sequence_id": sequence.sequence_id,
            "endpoint_row_id": sequence.endpoint.row_id,
            "symbol": sequence.symbol,
            "passive_side": sequence.passive_side,
            "day_index": sequence.day_index,
            "start_decision_index": sequence.start_decision_index,
            "end_decision_index": sequence.end_decision_index,
            "split": split_name,
            "horizon": model.horizon,
            "family": "causal_conv1d_lstm",
            "target": int(target),
            "uncalibrated_probability": float(p_raw),
            "calibrated_probability": float(p_cal),
        }
        for sequence, target, p_raw, p_cal in zip(sequences, y, raw, calibrated, strict=True)
    ]
    metrics_config = metric_config(config)
    return (
        rows,
        probability_metrics(y.astype(np.int64), raw, metrics_config),
        probability_metrics(y.astype(np.int64), calibrated, metrics_config),
    )


def slice_metrics(
    model: FittedTemporalModel,
    sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> dict[str, dict[str, object]]:
    slices: dict[str, list[TemporalSequence]] = {}
    for symbol in config.symbols:
        slices[f"instrument:{symbol}"] = [item for item in sequences if item.symbol == symbol]
    for side in ("bid", "ask"):
        slices[f"side:{side}"] = [item for item in sequences if item.passive_side == side]
    start = config.split_days.train + config.split_days.validation + config.split_days.calibration
    midpoint = start + config.split_days.engineering_holdout // 2
    slices["temporal:first_half"] = [
        item for item in sequences if start <= item.day_index < midpoint
    ]
    slices["temporal:second_half"] = [item for item in sequences if midpoint <= item.day_index]
    output: dict[str, dict[str, object]] = {}
    metric_cfg = metric_config(config)
    for name, subset in slices.items():
        x, y = sequence_matrix(subset, config, model.horizon)
        p = model.predict_calibrated(x)
        output[name] = asdict(probability_metrics(y.astype(np.int64), p, metric_cfg))
    return output


def decision_proxy(
    y: np.ndarray, probabilities: np.ndarray, config: TemporalModelConfig
) -> dict[str, float | int]:
    threshold = config.decision_proxy.aggressive_cost / config.decision_proxy.passive_depletion_cost
    aggressive = np.asarray(probabilities, dtype=np.float64) >= threshold
    target = np.asarray(y, dtype=np.float64)
    realized = np.where(
        aggressive,
        config.decision_proxy.aggressive_cost,
        target * config.decision_proxy.passive_depletion_cost,
    )
    oracle = np.minimum(
        np.full(len(target), config.decision_proxy.aggressive_cost, dtype=np.float64),
        target * config.decision_proxy.passive_depletion_cost,
    )
    return {
        "rows": len(target),
        "aggressive_threshold": threshold,
        "aggressive_fraction": float(aggressive.mean()),
        "mean_proxy_cost": float(realized.mean()),
        "oracle_mean_proxy_cost": float(oracle.mean()),
        "mean_proxy_regret": float((realized - oracle).mean()),
    }


def base_rate_proxy(
    sequences: list[TemporalSequence],
    horizon: str,
    train_prevalence: float,
    config: TemporalModelConfig,
) -> dict[str, float | int]:
    y = np.asarray(
        [sequence.endpoint.labels[HORIZON_TARGETS[horizon]] for sequence in sequences],
        dtype=np.int64,
    )
    p = np.full(len(y), train_prevalence, dtype=np.float64)
    return decision_proxy(y, p, config)


def _stressed_feature(feature: dict[str, int], config: TemporalModelConfig) -> dict[str, int]:
    stress = config.ood_feature_stress
    changed = dict(feature)
    changed["spread_ticks"] = max(1, feature["spread_ticks"] + stress.spread_add_ticks)
    for name in ("same_top1_lots", "same_top5_lots"):
        changed[name] = max(1, int(round(feature[name] * stress.same_depth_scale)))
    for name in ("opposite_top1_lots", "opposite_top5_lots"):
        changed[name] = max(1, int(round(feature[name] * stress.opposite_depth_scale)))
    same1 = changed["same_top1_lots"]
    opposite1 = changed["opposite_top1_lots"]
    same5 = changed["same_top5_lots"]
    opposite5 = changed["opposite_top5_lots"]
    changed["side_imbalance_top1_bps"] = math.trunc(
        10000 * (same1 - opposite1) / (same1 + opposite1)
    )
    changed["side_imbalance_top5_bps"] = math.trunc(
        10000 * (same5 - opposite5) / (same5 + opposite5)
    )
    changed["quote_age_ns"] = int(round(feature["quote_age_ns"] * stress.quote_age_scale))
    changed["time_since_last_trade_ns"] = int(
        round(feature["time_since_last_trade_ns"] * stress.trade_age_scale)
    )
    return changed


def stress_sequences(
    sequences: list[TemporalSequence], config: TemporalModelConfig
) -> list[TemporalSequence]:
    output: list[TemporalSequence] = []
    for sequence in sequences:
        rows = tuple(
            replace(row, feature=_stressed_feature(row.feature, config))
            for row in sequence.rows
        )
        output.append(replace(sequence, rows=rows))
    return output


def reverse_sequences(sequences: list[TemporalSequence]) -> list[TemporalSequence]:
    # Keep endpoint metadata/label fixed; reverse only feature history to form an engineering
    # temporal-order ablation. It is deliberately not presented as a market-realistic dataset.
    output: list[TemporalSequence] = []
    for sequence in sequences:
        reversed_features = [row.feature for row in reversed(sequence.rows)]
        rows = tuple(
            replace(row, feature=dict(feature))
            for row, feature in zip(sequence.rows, reversed_features, strict=True)
        )
        output.append(replace(sequence, rows=rows))
    return output


def ood_diagnostics(
    model: FittedTemporalModel,
    sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> dict[str, object]:
    metric_cfg = metric_config(config)
    x_id, y = sequence_matrix(sequences, config, model.horizon)
    id_probability = model.predict_calibrated(x_id)
    stressed = stress_sequences(sequences, config)
    x_stress, _ = sequence_matrix(stressed, config, model.horizon)
    stress_probability = model.predict_calibrated(x_stress)
    reversed_history = reverse_sequences(sequences)
    x_reverse, _ = sequence_matrix(reversed_history, config, model.horizon)
    reverse_probability = model.predict_calibrated(x_reverse)
    return {
        "status": "synthetic_engineering_perturbations_not_generalisation_claim",
        "in_distribution": asdict(
            probability_metrics(y.astype(np.int64), id_probability, metric_cfg)
        ),
        "feature_stress": asdict(
            probability_metrics(y.astype(np.int64), stress_probability, metric_cfg)
        ),
        "temporal_order_ablation": asdict(
            probability_metrics(y.astype(np.int64), reverse_probability, metric_cfg)
        ),
        "mean_abs_probability_shift_feature_stress": float(
            np.mean(np.abs(stress_probability - id_probability))
        ),
        "mean_abs_probability_shift_temporal_reversal": float(
            np.mean(np.abs(reverse_probability - id_probability))
        ),
    }


def temporal_model_card(
    model: FittedTemporalModel,
    config: TemporalModelConfig,
    candidates: list[CandidateResult],
) -> dict[str, object]:
    return {
        "schema_version": "temporal-model-card-v1",
        "step": 23,
        "family": "causal_conv1d_lstm",
        "architecture_rationale": (
            "compact causal convolution for local feature interactions plus LSTM "
            "for path dependence; "
            "adapted to the frozen engineered-feature contract rather than raw LOB tensors"
        ),
        "horizon": model.horizon,
        "feature_names": list(model.feature_names),
        "sequence_length": model.sequence_length,
        "conv_kernel_size": model.conv_kernel_size,
        "hyperparameters": asdict(model.hyperparameters),
        "selected_epoch": model.best_epoch,
        "hyperparameter_selection_segment": "validation_only",
        "validation_candidates": [
            {**asdict(item), "hyperparameters": asdict(item.hyperparameters)} for item in candidates
        ],
        "final_fit_segment": "train_plus_validation",
        "scaler_fit_segment": "train_only",
        "scaler": asdict(model.scaler),
        "calibration_segment": "calibration_only",
        "calibration_method": config.calibration_method,
        "calibration": asdict(model.calibrator),
        "training_prevalence": model.train_prevalence,
        "parameter_count": parameter_count(model.network),
        "research_status": "synthetic_validation_only_non_research",
        "selected_as_final_model": False,
        "selected_as_primary_horizon": False,
        "engineering_holdout_used_for_selection": False,
        "decision_proxy_used_for_selection": False,
        "locked_research_test_opened": False,
    }


def state_dict_payload(model: FittedTemporalModel) -> dict[str, object]:
    state: dict[str, object] = {}
    for name, tensor in model.network.state_dict().items():
        array = tensor.detach().cpu().numpy()
        state[name] = {
            "shape": list(array.shape),
            "values": [float(value) for value in array.reshape(-1)],
        }
    return {
        "schema_version": "temporal-model-weights-v1",
        "family": "causal_conv1d_lstm",
        "horizon": model.horizon,
        "state_dict": state,
    }


def load_model_from_payloads(
    card: dict[str, object], weights: dict[str, object], config: TemporalModelConfig
) -> FittedTemporalModel:
    if card.get("schema_version") != "temporal-model-card-v1":
        raise TemporalModelError("temporal model card schema changed")
    if weights.get("schema_version") != "temporal-model-weights-v1":
        raise TemporalModelError("temporal weights schema changed")
    hyper_raw = card["hyperparameters"]
    if not isinstance(hyper_raw, dict):
        raise TemporalModelError("model-card hyperparameters malformed")
    hyper = TemporalHyperparameters(**hyper_raw)  # type: ignore[arg-type]
    scaler_raw = card["scaler"]
    calibrator_raw = card["calibration"]
    if not isinstance(scaler_raw, dict) or not isinstance(calibrator_raw, dict):
        raise TemporalModelError("model-card scaler/calibration malformed")
    scaler = FeatureScaler(
        mean=tuple(float(value) for value in scaler_raw["mean"]),  # type: ignore[index]
        scale=tuple(float(value) for value in scaler_raw["scale"]),  # type: ignore[index]
    )
    calibrator = PlattCalibrator(
        intercept=float(calibrator_raw["intercept"]),  # type: ignore[index]
        slope=float(calibrator_raw["slope"]),  # type: ignore[index]
        epsilon=float(calibrator_raw.get("epsilon", 1e-9)),
    )
    _set_deterministic(_candidate_seed(config, str(card["horizon"]), "reload"))
    network = _network(config, hyper)
    state_raw = weights.get("state_dict")
    if not isinstance(state_raw, dict):
        raise TemporalModelError("temporal weights state_dict malformed")
    current = network.state_dict()
    rebuilt: dict[str, torch.Tensor] = {}
    if set(state_raw) != set(current):
        raise TemporalModelError("temporal weights names changed")
    for name, tensor in current.items():
        item = state_raw[name]
        if not isinstance(item, dict) or set(item) != {"shape", "values"}:
            raise TemporalModelError(f"temporal weight {name} malformed")
        shape = tuple(int(value) for value in item["shape"])  # type: ignore[index]
        values = np.asarray(item["values"], dtype=np.float32)  # type: ignore[index]
        if shape != tuple(tensor.shape) or values.size != tensor.numel():
            raise TemporalModelError(f"temporal weight {name} shape changed")
        rebuilt[name] = torch.from_numpy(values.reshape(shape))
    network.load_state_dict(rebuilt, strict=True)
    return FittedTemporalModel(
        horizon=str(card["horizon"]),
        hyperparameters=hyper,
        best_epoch=int(card["selected_epoch"]),
        scaler=scaler,
        calibrator=calibrator,
        train_prevalence=float(card["training_prevalence"]),
        feature_names=tuple(str(value) for value in card["feature_names"]),  # type: ignore[index]
        sequence_length=int(card["sequence_length"]),
        conv_kernel_size=int(card["conv_kernel_size"]),
        network=network,
    )


def benchmark_batch_one(
    model: FittedTemporalModel,
    sequence: TemporalSequence,
    config: TemporalModelConfig,
    repetitions: int = 200,
) -> dict[str, object]:
    if repetitions < 10:
        raise TemporalModelError("inference benchmark requires at least 10 repetitions")
    x, _ = sequence_matrix([sequence], config, model.horizon)
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
        "parameter_count": parameter_count(model.network),
        "sequence_length": config.sequence_length,
        "torch_threads": torch.get_num_threads(),
        "claim_status": "engineering_machine_specific_not_step30_performance_claim",
    }


def canonical_config_sha256(config: TemporalModelConfig) -> str:
    return hashlib.sha256(canonical_json_bytes(asdict(config))).hexdigest()


def sequence_reliability(
    model: FittedTemporalModel,
    sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> list[dict[str, object]]:
    x, y = sequence_matrix(sequences, config, model.horizon)
    return reliability_bins(
        y.astype(np.int64), model.predict_calibrated(x), config.ece_bins
    )
