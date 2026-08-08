from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import robust_execution.analysis.prediction_decision_value as pdv
from robust_execution.analysis.prediction_decision_value import (
    PredictionDecisionValueError,
    Step25Config,
    ablation_probabilities,
    action_distance,
    probability_metrics,
    relation_label,
    validate_config,
)


def valid_config() -> Step25Config:
    return Step25Config(
        schema_version="prediction-decision-value-engineering-config-v1",
        step=25,
        research_status="synthetic_validation_only_non_research",
        source_dataset="step23-temporal-deep-validation",
        prediction_family="causal_conv1d_lstm",
        candidate_horizons=("250ms", "1s", "5s"),
        ece_bins=10,
        weight_grid_bps=(0.0, 1000.0, 5000.0),
        primary_horizon_selected=False,
        final_model_family_selected=False,
        use_engineering_results_for_research_selection=False,
    )


def test_config_accepts_frozen_engineering_boundary() -> None:
    validate_config(valid_config())


@pytest.mark.parametrize(
    "mutation",
    [
        {"step": 24},
        {"research_status": "research"},
        {"candidate_horizons": ("1s", "5s", "10s")},
        {"weight_grid_bps": (100.0, 500.0)},
        {"weight_grid_bps": (0.0, 500.0, 100.0)},
        {"primary_horizon_selected": True},
        {"final_model_family_selected": True},
        {"use_engineering_results_for_research_selection": True},
    ],
)
def test_config_rejects_boundary_mutations(mutation: dict[str, object]) -> None:
    with pytest.raises(PredictionDecisionValueError):
        validate_config(replace(valid_config(), **mutation))


def test_ablation_probabilities_stay_within_day_symbol_side_groups() -> None:
    rows = [
        {
            "day_index": 80,
            "symbol": "BTCUSDT",
            "passive_side": "bid",
            "end_decision_index": 7,
            "calibrated_probability": 0.1,
            "uncalibrated_probability": 0.11,
            "target": 0,
        },
        {
            "day_index": 80,
            "symbol": "BTCUSDT",
            "passive_side": "bid",
            "end_decision_index": 8,
            "calibrated_probability": 0.2,
            "uncalibrated_probability": 0.21,
            "target": 1,
        },
        {
            "day_index": 80,
            "symbol": "BTCUSDT",
            "passive_side": "ask",
            "end_decision_index": 7,
            "calibrated_probability": 0.8,
            "uncalibrated_probability": 0.81,
            "target": 1,
        },
    ]
    result = ablation_probabilities(rows, 0.4)
    assert result["shuffled_within_day_instrument"].tolist() == [0.2, 0.1, 0.8]
    assert result["stale"].tolist() == [0.4, 0.1, 0.4]
    assert result["perfect_event_oracle"].tolist() == [0.0, 1.0, 1.0]


def test_probability_metrics_reward_perfect_event_oracle() -> None:
    result = probability_metrics([0, 1, 0, 1], [0, 1, 0, 1], 10)
    assert result["log_loss"] < 1e-8
    assert result["brier"] < 1e-16
    assert result["roc_auc"] == 1.0
    assert result["pr_auc"] == 1.0


def test_probability_metrics_reject_misaligned_vectors() -> None:
    with pytest.raises(PredictionDecisionValueError):
        probability_metrics([0, 1], [0.2], 10)


def test_action_distance_counts_substitutions_and_length_difference() -> None:
    assert action_distance(["a", "b", "c"], ["a", "x"]) == 2
    assert action_distance(["a"], ["a"]) == 0


def test_relationship_labels_prediction_change_separately_from_decision_change() -> None:
    worse = {"log_loss": 0.7}
    better = {"log_loss": 0.6}
    same_decision = {"actions": ["passive"]}
    changed_decision = {"actions": ["aggressive"]}
    assert (
        relation_label(worse, better, same_decision, same_decision)
        == "prediction_improved_decision_unchanged"
    )
    assert (
        relation_label(worse, better, same_decision, changed_decision)
        == "prediction_improved_decision_changed"
    )
    assert (
        relation_label(better, worse, same_decision, changed_decision)
        == "prediction_not_improved_decision_changed"
    )


def test_probability_metrics_are_finite_for_constant_base_rate() -> None:
    result = probability_metrics([0, 1, 0, 1], np.full(4, 0.5), 10)
    assert np.isfinite(result["log_loss"])
    assert np.isfinite(result["brier"])
    assert result["roc_auc"] == 0.5


ROOT = Path(__file__).resolve().parents[2]


def _episode(actions: list[str], shortfall: int) -> dict[str, object]:
    return {"actions": actions, "implementation_shortfall_bps": shortfall, "complete": True}


def _fake_controller_report(weight: float, *, locked: bool = False) -> dict[str, object]:
    baseline_actions = ["passive", "aggressive"]
    payload: dict[str, object] = {
        "locked_research_test_opened": locked,
        "non_ml_mpc": _episode(baseline_actions, -10),
        "horizons": {},
    }
    for horizon in pdv.HORIZONS:
        calibrated_actions = baseline_actions if weight < 5000 else ["aggressive"]
        oracle_actions = baseline_actions if weight < 1000 else ["aggressive"]
        payload["horizons"][horizon] = {
            "calibrated": _episode(calibrated_actions, -10 if weight < 5000 else 5),
            "training_base_rate_ablation": _episode(baseline_actions, -10),
            "shuffled_within_day_instrument_ablation": _episode(baseline_actions, -10),
            "stale_ablation": _episode(baseline_actions, -10),
            "uncalibrated_ablation": _episode(baseline_actions, -10),
            "perfect_event_oracle_ablation": _episode(oracle_actions, -10 if weight < 1000 else 0),
            "prediction_weight_zero_ablation": _episode(baseline_actions, -10),
        }
    return {"payload": payload}


def test_load_config_and_hash_helpers_use_committed_config(tmp_path: Path) -> None:
    config = pdv.load_config(
        ROOT / "configs/analysis/step25_prediction_decision_value_engineering.json"
    )
    assert config.step == 25
    assert config.weight_grid_bps[0] == 0.0
    target = tmp_path / "hash.txt"
    target.write_bytes(b"abc")
    assert pdv.sha256_bytes(b"abc") == pdv.sha256_path(target)
    assert pdv.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_validate_config_rejects_small_ece_and_nonfinite_weight() -> None:
    with pytest.raises(PredictionDecisionValueError):
        validate_config(replace(valid_config(), ece_bins=1))
    with pytest.raises(PredictionDecisionValueError):
        validate_config(replace(valid_config(), weight_grid_bps=(0.0, float("inf"))))


def test_load_prediction_analysis_reads_full_committed_holdout() -> None:
    config = pdv.load_config(
        ROOT / "configs/analysis/step25_prediction_decision_value_engineering.json"
    )
    analysis, sources = pdv.load_prediction_analysis(ROOT, config)
    assert set(analysis) == set(pdv.HORIZONS)
    assert all(analysis[horizon]["rows"] == 400 for horizon in pdv.HORIZONS)
    assert all(
        analysis[horizon]["metrics"]["perfect_event_oracle"]["log_loss"] < 1e-7
        for horizon in pdv.HORIZONS
    )
    assert len(sources["step23_report_sha256"]) == 64


def test_controller_report_passes_weight_through_environment(tmp_path: Path) -> None:
    script = tmp_path / "controller.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "print(json.dumps({'weight': os.environ['RE_ML_MPC_WEIGHT_BPS']}))\n"
    )
    script.chmod(0o755)
    assert pdv._controller_report(script, 250.0)["weight"] == "250.0"


def test_load_decision_sweep_detects_first_change(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(valid_config(), weight_grid_bps=(0.0, 1000.0, 5000.0))
    monkeypatch.setattr(
        pdv, "_controller_report", lambda _exe, weight: _fake_controller_report(weight)
    )
    sweep = pdv.load_decision_sweep(Path("unused"), config)
    assert sweep["baseline_non_ml"]["implementation_shortfall_bps"] == -10
    for horizon in pdv.HORIZONS:
        assert (
            sweep["horizons"][horizon]["calibrated_model"][
                "first_grid_weight_with_action_change_bps"
            ]
            == 5000.0
        )
        assert (
            sweep["horizons"][horizon]["perfect_event_oracle"][
                "first_grid_weight_with_action_change_bps"
            ]
            == 1000.0
        )
        assert (
            sweep["horizons"][horizon]["training_base_rate"][
                "first_grid_weight_with_action_change_bps"
            ]
            is None
        )


def test_load_decision_sweep_rejects_locked_test(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(valid_config(), weight_grid_bps=(0.0,))
    monkeypatch.setattr(
        pdv,
        "_controller_report",
        lambda _exe, weight: _fake_controller_report(weight, locked=True),
    )
    with pytest.raises(PredictionDecisionValueError, match="locked research test"):
        pdv.load_decision_sweep(Path("unused"), config)


def test_load_decision_sweep_rejects_broken_zero_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(valid_config(), weight_grid_bps=(0.0,))
    report = _fake_controller_report(0.0)
    report["payload"]["horizons"]["250ms"]["prediction_weight_zero_ablation"]["actions"] = ["wrong"]
    monkeypatch.setattr(pdv, "_controller_report", lambda _exe, _weight: report)
    with pytest.raises(PredictionDecisionValueError, match="zero-weight"):
        pdv.load_decision_sweep(Path("unused"), config)


def test_build_relationships_summary_and_report(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(valid_config(), weight_grid_bps=(0.0, 1000.0, 5000.0))
    prediction = {
        horizon: {
            "metrics": {
                "calibrated_model": {"log_loss": 0.4},
                "training_base_rate": {"log_loss": 0.5},
                "shuffled_within_day_instrument": {"log_loss": 0.6},
                "stale": {"log_loss": 0.55},
                "uncalibrated_model": {"log_loss": 0.45},
                "perfect_event_oracle": {"log_loss": 0.0},
            }
        }
        for horizon in pdv.HORIZONS
    }
    monkeypatch.setattr(
        pdv, "_controller_report", lambda _exe, weight: _fake_controller_report(weight)
    )
    decision = pdv.load_decision_sweep(Path("unused"), config)
    relationships = pdv.build_relationships(prediction, decision)
    summary = pdv.build_engineering_summary(prediction, decision, relationships)
    assert summary["prediction_metric_improvement_without_decision_change_observed"] is True
    assert summary["perfect_label_oracle_can_worsen_execution_fixture"] is True
    assert summary["any_changed_action_improved_implementation_shortfall_fixture"] is False

    monkeypatch.setattr(pdv, "load_prediction_analysis", lambda _root, _config: (prediction, {}))
    monkeypatch.setattr(pdv, "load_decision_sweep", lambda _exe, _config: decision)
    report = pdv.build_report(ROOT, config, Path("unused"))
    assert report["payload"]["step"] == 25
    assert report["payload"]["primary_horizon_selected"] is False
    assert len(report["sha256"]) == 64


def test_probability_metrics_single_class_has_no_auc() -> None:
    result = probability_metrics([0, 0], [0.2, 0.3], 5)
    assert result["roc_auc"] is None
    assert result["pr_auc"] is None
