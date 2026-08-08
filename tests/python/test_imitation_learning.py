from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from robust_execution.imitation.learning import (
    ACTION_FRACTIONS,
    FEATURES,
    ImitationError,
    _apply_action,
    _episode_paths,
    _prediction_probability,
    _reconstruct_model,
    canonical_json,
    load_config,
    validate_step26_report,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/imitation/step26_imitation_engineering.json"
REPORT = ROOT / "data/sample/imitation/step26-imitation-validation/report.json"
POLICY = ROOT / "data/sample/imitation/step26-imitation-validation/policy.json"


def test_step26_config_is_engineering_only() -> None:
    config = load_config(CONFIG)
    assert config.step == 26
    assert config.research_status == "synthetic_validation_only_non_research"
    assert set(config.episode_counts) == {
        "train",
        "validation",
        "correction",
        "engineering_holdout",
        "ood",
    }


def test_step26_config_rejects_research_boundary_change(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["research_status"] = "historical_research"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ImitationError, match="research boundary"):
        load_config(path)


def test_prediction_probability_is_bounded_and_causal_current_state_only() -> None:
    market = {
        "bid": 99,
        "ask": 101,
        "bid_quantity": 30,
        "ask_quantity": 200,
        "favorable": 0,
    }
    first = _prediction_probability(market, 20, 2, 6)
    second = _prediction_probability(dict(market), 20, 2, 6)
    assert 0.05 <= first <= 0.95
    assert first == second


def test_episode_paths_are_deterministic_and_ood_is_wider() -> None:
    first = _episode_paths("train", 5, 6, False)
    second = _episode_paths("train", 5, 6, False)
    ood = _episode_paths("ood", 5, 6, True)
    assert first == second
    id_spreads = [row["ask"] - row["bid"] for path in first for row in path["market"]]
    ood_spreads = [row["ask"] - row["bid"] for path in ood for row in path["market"]]
    assert max(ood_spreads) > max(id_spreads)


@pytest.mark.parametrize("action", sorted(ACTION_FRACTIONS))
def test_action_contract_is_valid(action: str) -> None:
    quantity, price = _apply_action(action, 100, 99, 101)
    assert 0 <= quantity <= 100
    if action.startswith("passive"):
        assert price == 99.0
    elif action.startswith("aggressive"):
        assert price == 101.0
    else:
        assert quantity == 0 and price == 0.0


def test_policy_artifact_reconstructs_exactly() -> None:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    model = _reconstruct_model(payload)
    assert len(model.scaler_mean) == len(FEATURES)
    matrix = np.vstack([model.scaler_mean, model.scaler_mean + 0.1 * model.scaler_scale])
    first = model.probabilities(matrix)
    second = _reconstruct_model(json.loads(canonical_json(payload))).probabilities(matrix)
    assert np.array_equal(first, second)
    assert np.allclose(first.sum(axis=1), 1.0)


def test_committed_report_passes_semantic_validation() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    validate_step26_report(report)
    assert report["covariate_shift"]["dagger_triggered"] is True
    assert report["covariate_shift"]["dagger_rounds"] == 1
    assert report["data"]["correction_rows_added"] > 0


def test_dagger_improves_validation_rollout_agreement() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    shift = report["covariate_shift"]
    assert (
        shift["final_validation_raw_action_agreement"]
        > shift["initial_validation_raw_action_agreement"]
    )


def test_engineering_holdout_retains_teacher_quality() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    block = report["evaluation"]["engineering_holdout"]
    assert block["student_raw"]["raw_action_agreement"] == 1.0
    assert block["student_raw"]["mean_shortfall_delta_vs_teacher_bps"] == 0.0
    assert block["student_raw"]["p95_shortfall_delta_vs_teacher_bps"] == 0.0


def test_ood_negative_result_and_fallback_are_preserved() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    block = report["evaluation"]["ood"]
    raw = block["student_raw"]
    fallback = block["student_with_teacher_fallback"]
    assert raw["raw_action_agreement"] < 0.8
    assert fallback["final_action_agreement"] > raw["raw_action_agreement"]
    assert fallback["fallback_rate"] > 0.5
    assert fallback["final_action_agreement"] < 1.0


def test_report_keeps_research_and_rl_locked() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["research_selections"] == {
        "historical_test_opened": False,
        "research_policy_selected": False,
        "rl_started": False,
    }
    assert len(report["teacher"]["training_class_counts"]) >= 3


def test_fallback_threshold_is_validation_only() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["fallback"]["threshold_selected_on_validation_only"] is True
    assert report["fallback"]["kind"] == "teacher_mpc_fallback_engineering_only"


def _fake_oracle(_executable: Path, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for row in rows:
        bid = float(row["bid"])
        ask = float(row["ask"])
        same = float(row["bid_quantity"])
        opposite = float(row["ask_quantity"])
        queue_share = same / max(1.0, same + opposite)
        pressure = 0.8 if int(row["favorable_passive_flow"]) else 0.2
        fill_probability = min(
            1.0,
            max(0.0, 0.5 + 0.45 * (0.5 - queue_share) + 0.35 * (pressure - 0.5)),
        )
        start = float(row["start"])
        deadline = float(row["deadline"])
        now = float(row["now"])
        horizon = deadline - start
        elapsed = min(1.0, max(0.0, (now - start) / horizon))
        filled_fraction = float(row["filled"]) / float(row["total"])
        remaining_fraction = 1.0 - filled_fraction
        progress_lag = max(0.0, elapsed - filled_fraction)
        probability = float(row["prediction_probability"])
        if probability > 0.78:
            action = "aggressive_100"
        elif probability > 0.68:
            action = "aggressive_50"
        elif progress_lag > 0.22:
            action = "aggressive_25"
        else:
            action = "passive_50"
        outputs.append(
            {
                "episode_id": str(row["episode_id"]),
                "step": str(row["step"]),
                "decision_id": str(row["decision_id"]),
                "action_label": action,
                "teacher_latency_ns": "1000",
                "midpoint_ticks": str((bid + ask) / 2.0),
                "spread_ticks": str(ask - bid),
                "same_side_best_lots": str(same),
                "opposite_side_best_lots": str(opposite),
                "same_side_queue_share": str(queue_share),
                "passive_fill_pressure": str(pressure),
                "passive_fill_probability": str(fill_probability),
                "elapsed_fraction": str(elapsed),
                "filled_fraction": str(filled_fraction),
                "remaining_fraction": str(remaining_fraction),
                "progress_lag": str(progress_lag),
                "time_remaining_fraction": str(1.0 - elapsed),
                "prediction_probability": str(probability),
                "objective_bps": "0.0",
            }
        )
    return outputs


def test_full_step26_pipeline_with_fake_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import robust_execution.imitation.learning as learning

    monkeypatch.setattr(learning, "_oracle", _fake_oracle)
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["episode_counts"] = {
        "train": 12,
        "validation": 10,
        "correction": 10,
        "engineering_holdout": 10,
        "ood": 10,
    }
    raw["steps_per_episode"] = 4
    raw["hidden_units"] = [4]
    raw["alphas"] = [0.01]
    raw["validation_dagger_agreement_floor"] = 1.0
    raw["validation_shift_trigger"] = 0.0001
    config = tmp_path / "config.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    output = tmp_path / "artifacts"
    report = learning.generate_step26_artifacts(
        tmp_path,
        Path("unused-oracle"),
        config,
        output,
    )
    learning.validate_step26_report(report)
    assert (output / "report.json").is_file()
    assert (output / "policy.json").is_file()
    assert report["data"]["teacher_rows"]["train"] == 48
    assert report["model_selection"]["hyperparameters_frozen_before_correction"] is True
    assert report["research_selections"]["rl_started"] is False


def test_validation_rejects_incomplete_student() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["evaluation"]["engineering_holdout"]["student_raw"]["completion_rate"] = 0.9
    with pytest.raises(ImitationError, match="hard completion"):
        validate_step26_report(report)


def test_validation_rejects_invalid_action_rate() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["evaluation"]["ood"]["student_raw"]["invalid_action_rate"] = 0.1
    with pytest.raises(ImitationError, match="invalid imitation action"):
        validate_step26_report(report)


def test_validation_rejects_research_selection() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["research_selections"]["research_policy_selected"] = True
    with pytest.raises(ImitationError, match="research boundary"):
        validate_step26_report(report)
