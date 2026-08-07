from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

import numpy as np
import pytest

from robust_execution.prediction.simple_model_artifacts import (
    verify_simple_model_fixture,
    write_simple_model_fixture,
)
from robust_execution.prediction.simple_models import (
    HORIZON_TARGETS,
    FittedSimpleModel,
    SimpleModelError,
    TrainOnlyScaledEstimator,
    TrainingRow,
    fit_selected_model,
    generate_engineering_training_rows,
    load_serialized_model,
    load_simple_model_config,
    prediction_rows,
    probability_metrics,
    reliability_bins,
    select_hyperparameters,
    serialize_model,
    split_for_day,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/models/step22_simple_models_engineering.json"


def _config():
    return load_simple_model_config(CONFIG)


def _rows():
    config = _config()
    rows = generate_engineering_training_rows(config)
    split = {
        name: [row for row in rows if split_for_day(row.day_index, config.split_days) == name]
        for name in ("train", "validation", "calibration", "engineering_holdout")
    }
    return config, rows, split


def test_config_and_chronological_split() -> None:
    config, rows, split = _rows()
    assert len(rows) == 800
    assert {key: len(value) for key, value in split.items()} == {
        "train": 400,
        "validation": 160,
        "calibration": 80,
        "engineering_holdout": 160,
    }
    assert tuple(rows[0].feature) == config.feature_names
    for horizon, target in HORIZON_TARGETS.items():
        assert all(row.labels[target] in {0, 1} for row in rows), horizon
        assert all(
            row.labels["quote_depletion_250ms"]
            <= row.labels["quote_depletion_1s"]
            <= row.labels["quote_depletion_5s"]
            for row in rows
        )


def test_reject_unsafe_config_variants(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    variants = [
        ("selected_horizon", "1s"),
        ("final_model_selection_allowed", True),
        ("use_evaluation_for_selection", True),
        ("candidate_horizons", ["250ms", "1s"]),
        ("symbols", ["BTCUSDT"]),
        ("feature_names", raw["feature_names"][:-1]),
        ("calibration_method", "isotonic"),
    ]
    for field, value in variants:
        changed = dict(raw)
        changed[field] = value
        path = tmp_path / f"bad-{field}.json"
        path.write_text(json.dumps(changed))
        with pytest.raises(SimpleModelError):
            load_simple_model_config(path)
    research = dict(raw)
    research["mode"] = "research"
    path = tmp_path / "bad-research.json"
    path.write_text(json.dumps(research))
    with pytest.raises(SimpleModelError, match="previously frozen"):
        load_simple_model_config(path)


def test_hyperparameter_selection_ignores_calibration_and_holdout_labels() -> None:
    config, _, split = _rows()
    selected, candidates = select_hyperparameters(
        "logistic", "1s", split["train"], split["validation"], config
    )
    mutated_calibration = [
        replace(
            row,
            labels={
                **row.labels,
                "quote_depletion_1s": 1 - row.labels["quote_depletion_1s"],
            },
        )
        for row in split["calibration"]
    ]
    mutated_holdout = [
        replace(
            row,
            labels={
                **row.labels,
                "quote_depletion_1s": 1 - row.labels["quote_depletion_1s"],
            },
        )
        for row in split["engineering_holdout"]
    ]
    selected_again, candidates_again = select_hyperparameters(
        "logistic", "1s", split["train"], split["validation"], config
    )
    assert selected == selected_again
    assert candidates == candidates_again
    assert mutated_calibration != split["calibration"]
    assert mutated_holdout != split["engineering_holdout"]


def test_scaler_is_training_only_after_final_refit() -> None:
    config, _, split = _rows()
    selected, _ = select_hyperparameters(
        "logistic", "1s", split["train"], split["validation"], config
    )
    model = fit_selected_model(
        "logistic",
        "1s",
        selected,
        split["train"],
        split["validation"],
        split["calibration"],
        config,
    )
    assert isinstance(model.estimator, TrainOnlyScaledEstimator)
    train_matrix = np.asarray(
        [[row.feature[name] for name in config.feature_names] for row in split["train"]],
        dtype=np.float64,
    )
    dev_matrix = np.asarray(
        [
            [row.feature[name] for name in config.feature_names]
            for row in split["train"] + split["validation"]
        ],
        dtype=np.float64,
    )
    assert np.allclose(model.estimator.scaler.mean_, train_matrix.mean(axis=0))
    assert not np.allclose(model.estimator.scaler.mean_, dev_matrix.mean(axis=0), atol=1e-12)


def test_calibration_changes_only_calibrator_not_base_estimator() -> None:
    config, _, split = _rows()
    selected, _ = select_hyperparameters(
        "gradient_boosted_trees", "5s", split["train"], split["validation"], config
    )
    original = fit_selected_model(
        "gradient_boosted_trees",
        "5s",
        selected,
        split["train"],
        split["validation"],
        split["calibration"],
        config,
    )
    changed_rows = [
        replace(
            row,
            labels={
                **row.labels,
                "quote_depletion_5s": 1 - row.labels["quote_depletion_5s"],
            },
        )
        for row in split["calibration"]
    ]
    changed = fit_selected_model(
        "gradient_boosted_trees",
        "5s",
        selected,
        split["train"],
        split["validation"],
        changed_rows,
        config,
    )
    x = np.asarray(
        [
            [row.feature[name] for name in config.feature_names]
            for row in split["engineering_holdout"]
        ],
        dtype=np.float64,
    )
    assert np.allclose(original.predict_uncalibrated(x), changed.predict_uncalibrated(x))
    assert not np.allclose(original.predict_calibrated(x), changed.predict_calibrated(x))


def test_base_rate_uses_training_prevalence_only() -> None:
    config, _, split = _rows()
    model = fit_selected_model(
        "base_rate", "250ms", {}, split["train"], split["validation"], split["calibration"], config
    )
    expected = np.mean([row.labels["quote_depletion_250ms"] for row in split["train"]])
    assert model.constant_probability == pytest.approx(expected)


def test_all_required_model_families_fit_and_score() -> None:
    config, _, split = _rows()
    for family in ("base_rate", "logistic", "gradient_boosted_trees", "simple_mlp"):
        selected, candidates = select_hyperparameters(
            family, "1s", split["train"], split["validation"], config
        )
        assert candidates
        model = fit_selected_model(
            family,
            "1s",
            selected,
            split["train"],
            split["validation"],
            split["calibration"],
            config,
        )
        predictions, raw, calibrated = prediction_rows(
            model, split["engineering_holdout"], config, "engineering_holdout"
        )
        assert len(predictions) == 160
        assert raw.rows == calibrated.rows == 160
        assert 0.0 <= calibrated.brier <= 1.0
        assert calibrated.log_loss > 0.0


def test_probability_metrics_and_reliability_edge_cases() -> None:
    config = _config()
    y = np.asarray([0, 0, 1, 1], dtype=np.int64)
    p = np.asarray([0.1, 0.3, 0.7, 0.9], dtype=np.float64)
    metrics = probability_metrics(y, p, config)
    assert metrics.rows == 4
    assert metrics.positives == 2
    assert metrics.roc_auc == pytest.approx(1.0)
    bins = reliability_bins(y, p, 4)
    assert sum(int(item["count"]) for item in bins) == 4
    with pytest.raises(SimpleModelError):
        reliability_bins(y, p, 1)


def test_model_serialization_roundtrip(tmp_path: Path) -> None:
    config, _, split = _rows()
    selected, _ = select_hyperparameters(
        "logistic", "1s", split["train"], split["validation"], config
    )
    model = fit_selected_model(
        "logistic",
        "1s",
        selected,
        split["train"],
        split["validation"],
        split["calibration"],
        config,
    )
    path = tmp_path / "model.pkl"
    serialize_model(model, path)
    loaded = load_serialized_model(path)
    x = np.asarray(
        [
            [row.feature[name] for name in config.feature_names]
            for row in split["engineering_holdout"][:8]
        ],
        dtype=np.float64,
    )
    assert np.array_equal(model.predict_calibrated(x), loaded.predict_calibrated(x))


def test_fixture_write_verify_rerun_and_tamper(tmp_path: Path) -> None:
    config = _config()
    first = write_simple_model_fixture(config, tmp_path / "a")
    second = write_simple_model_fixture(config, tmp_path / "b")
    assert verify_simple_model_fixture(first, config) == {
        "status": "ok",
        "rows": 800,
        "models": 12,
        "horizons": 3,
    }
    assert (first.parent / "report.json").read_bytes() == (
        second.parent / "report.json"
    ).read_bytes()
    assert verify_simple_model_fixture(second, config)["models"] == 12
    prediction = (
        first.parent
        / "models/1s/logistic/tables/engineering_holdout_predictions/columns.json.gz"
    )
    original = prediction.read_bytes()
    prediction.write_bytes(original + b"x")
    with pytest.raises(SimpleModelError, match="artifact verification"):
        verify_simple_model_fixture(first, config)


def test_additional_config_failure_paths(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    cases: list[tuple[str, object]] = [
        ("schema_version", "bad"),
        ("mode", "invalid"),
        ("rows_per_symbol_side_day", 0),
        ("random_seed", -1),
        ("ece_bins", 1),
        ("precision_recall_thresholds", [0.5, 0.5]),
        ("precision_recall_thresholds", []),
        ("hyperparameters", []),
    ]
    for field, value in cases:
        changed = dict(raw)
        changed[field] = value
        path = tmp_path / f"bad2-{field}.json"
        path.write_text(json.dumps(changed))
        with pytest.raises(SimpleModelError):
            load_simple_model_config(path)
    path = tmp_path / "bad-json.json"
    path.write_text("{")
    with pytest.raises(SimpleModelError, match="cannot read"):
        load_simple_model_config(path)
    path.write_text("[]")
    with pytest.raises(SimpleModelError, match="must be an object"):
        load_simple_model_config(path)
    with pytest.raises(SimpleModelError, match="cannot read"):
        load_simple_model_config(tmp_path / "missing.json")


def test_hyperparameter_and_split_failure_paths() -> None:
    config, _, split = _rows()
    with pytest.raises(SimpleModelError, match="day_index"):
        split_for_day(100, config.split_days)
    with pytest.raises(SimpleModelError, match="unknown prediction horizon"):
        select_hyperparameters(
            "logistic", "bad", split["train"], split["validation"], config
        )
    with pytest.raises(SimpleModelError, match="unsupported model family"):
        select_hyperparameters(
            "unsupported",  # type: ignore[arg-type]
            "1s",
            split["train"],
            split["validation"],
            config,
        )


def test_fitted_model_guard_paths() -> None:
    config = _config()
    broken_base = FittedSimpleModel(
        family="base_rate",
        horizon="1s",
        hyperparameters={},
        estimator=None,
        constant_probability=None,
        calibrator=None,
        train_prevalence=0.5,
        feature_names=config.feature_names,
    )
    with pytest.raises(SimpleModelError, match="constant probability"):
        broken_base.predict_uncalibrated(np.zeros((1, 20)))
    broken_model = FittedSimpleModel(
        family="logistic",
        horizon="1s",
        hyperparameters={},
        estimator=None,
        constant_probability=None,
        calibrator=None,
        train_prevalence=0.5,
        feature_names=config.feature_names,
    )
    with pytest.raises(SimpleModelError, match="predict_proba"):
        broken_model.predict_uncalibrated(np.zeros((1, 20)))


def test_training_row_validation_rejects_corruption() -> None:
    config, rows, _ = _rows()
    from robust_execution.prediction.simple_models import validate_training_rows

    with pytest.raises(SimpleModelError, match="row count"):
        validate_training_rows(rows[:-1], config)
    duplicate = list(rows)
    duplicate[-1] = replace(duplicate[-1], row_id=duplicate[0].row_id)
    with pytest.raises(SimpleModelError, match="duplicate"):
        validate_training_rows(duplicate, config)
    malformed = list(rows)
    malformed[0] = replace(malformed[0], symbol="DOGEUSDT")
    with pytest.raises(SimpleModelError, match="symbol/side"):
        validate_training_rows(malformed, config)
    malformed = list(rows)
    feature = dict(malformed[0].feature)
    feature.pop(config.feature_names[-1])
    malformed[0] = replace(malformed[0], feature=feature)
    with pytest.raises(SimpleModelError, match="feature columns"):
        validate_training_rows(malformed, config)
    malformed = list(rows)
    labels = dict(malformed[0].labels)
    labels["quote_depletion_250ms"] = 1
    labels["quote_depletion_1s"] = 0
    malformed[0] = replace(malformed[0], labels=labels)
    with pytest.raises(SimpleModelError, match="nested"):
        validate_training_rows(malformed, config)


def test_metrics_failure_paths() -> None:
    config = _config()
    with pytest.raises(SimpleModelError, match="empty"):
        probability_metrics(np.asarray([], dtype=np.int64), np.asarray([], dtype=float), config)
    from robust_execution.prediction.simple_models import _fit_platt

    with pytest.raises(SimpleModelError, match="both classes"):
        _fit_platt(np.asarray([0.1, 0.2]), np.asarray([0, 0], dtype=np.int64))


def test_bad_model_pickle_and_manifest_paths(tmp_path: Path) -> None:
    from robust_execution.prediction.simple_models import load_serialized_model

    bad = tmp_path / "bad.pkl"
    bad.write_bytes(b"not a pickle")
    with pytest.raises(SimpleModelError, match="cannot load"):
        load_serialized_model(bad)
    config = _config()
    manifest = write_simple_model_fixture(config, tmp_path / "fixture")
    raw = json.loads(manifest.read_text())
    raw["research_status"] = "research"
    manifest.write_text(json.dumps(raw))
    with pytest.raises(SimpleModelError, match="research boundary"):
        verify_simple_model_fixture(manifest, config)
