from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

import robust_execution.robustness.matrix as robustness_matrix
from robust_execution.rl.ppo import (
    TRAIN_REGIMES,
    SyntheticExecutionEnv,
    twap_policy,
)
from robust_execution.rl.ppo import (
    load_config as load_rl,
)
from robust_execution.robustness.matrix import (
    RobustnessError,
    StressCase,
    _compute_panel,
    _dimension_registry,
    _load_policies,
    _metrics,
    _paired_seeds,
    _prediction_panel,
    _queue_panel,
    _ranking_summary,
    _regime_for_case,
    _rl_config_for_case,
    generate_step28_artifacts,
    load_config,
    run_stress_episode,
    stress_cases,
    validate_config,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/robustness/step28_robustness_engineering.json"
RL_CONFIG = ROOT / "configs/rl/step27_ppo_engineering.json"


def test_config_and_registered_dimensions() -> None:
    config = load_config(CONFIG)
    assert config.step == 28
    assert len(config.ppo_seeds) == 5
    required = {
        "latency",
        "decision_grid",
        "liquidity",
        "spread",
        "volatility",
        "queue",
        "fees_rebates",
        "parent_size",
        "horizon",
        "impact",
        "prediction",
        "data_quality",
        "distribution",
        "compute",
        "simulator_mismatch",
    }
    assert set(_dimension_registry()) == required
    assert len(stress_cases()) == 43


def test_config_failures() -> None:
    cfg = load_config(CONFIG)
    with pytest.raises(RobustnessError):
        validate_config(replace(cfg, step=27))
    with pytest.raises(RobustnessError):
        validate_config(replace(cfg, episode_count=2))
    with pytest.raises(RobustnessError):
        validate_config(replace(cfg, ppo_seeds=(1, 2)))
    with pytest.raises(RobustnessError):
        validate_config(replace(cfg, compute_budgets_ms=(0.1, 0.05)))
    with pytest.raises(RobustnessError):
        validate_config(replace(cfg, formal_statistics_deferred_to_step29=False))


def test_default_step28_environment_extension_preserves_step27_path() -> None:
    cfg = load_rl(RL_CONFIG)
    left = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[1], seed=45)
    right = SyntheticExecutionEnv(
        cfg,
        regime=TRAIN_REGIMES[1],
        seed=45,
        market_time_scale=1.0,
        impact_exponent=2.0,
    )
    assert np.array_equal(left.reset(), right.reset())
    for _ in range(3):
        left_result = left.step(5)
        right_result = right.step(5)
        assert left_result[1:] == right_result[1:]
        if left_result[2]:
            break


def test_stress_extensions_change_market_economics() -> None:
    cfg = load_rl(RL_CONFIG)
    central = StressCase("central", "central", "central")
    mismatch = StressCase(
        "mismatch", "simulator_mismatch", "form", market_time_scale=2.0, impact_exponent=1.0
    )
    left = run_stress_episode(cfg, case=central, episode_seed=91, policy=twap_policy)
    right = run_stress_episode(cfg, case=mismatch, episode_seed=91, policy=twap_policy)
    assert float(left["cost_bps"]) != float(right["cost_bps"])


def test_data_loss_is_deterministic_and_recorded() -> None:
    cfg = load_rl(RL_CONFIG)
    case = StressCase("drop", "data_quality", "drop", observation_drop_probability=0.5)
    first = run_stress_episode(cfg, case=case, episode_seed=99, policy=twap_policy)
    second = run_stress_episode(cfg, case=case, episode_seed=99, policy=twap_policy)
    assert first == second
    assert int(first["dropped_observations"]) > 0


def test_delayed_observations_are_recorded() -> None:
    cfg = load_rl(RL_CONFIG)
    case = StressCase("delay", "data_quality", "delay", observation_delay_steps=2)
    row = run_stress_episode(cfg, case=case, episode_seed=101, policy=twap_policy)
    assert int(row["delayed_observations"]) > 0


def test_case_transformers_apply_only_registered_fields() -> None:
    cfg = load_rl(RL_CONFIG)
    case = StressCase("thin", "liquidity", "thin", depth_lots=30, parent_lots=25)
    regime = _regime_for_case(case)
    changed = _rl_config_for_case(cfg, case)
    assert regime.depth_lots == 30
    assert regime.spread_ticks == TRAIN_REGIMES[1].spread_ticks
    assert changed.parent_lots == 25
    assert changed.steps_per_episode == cfg.steps_per_episode


def test_metrics_require_completed_episode_rows() -> None:
    rows = [
        {
            "cost_bps": 1.0,
            "completed": True,
            "steps": 2,
            "invalid_actions": 0,
            "dropped_observations": 1,
            "delayed_observations": 0,
            "actions": dict.fromkeys(
                (
                    "wait",
                    "passive_25",
                    "passive_50",
                    "aggressive_25",
                    "aggressive_50",
                    "aggressive_100",
                ),
                0,
            ),
        },
        {
            "cost_bps": 3.0,
            "completed": True,
            "steps": 2,
            "invalid_actions": 0,
            "dropped_observations": 0,
            "delayed_observations": 1,
            "actions": dict.fromkeys(
                (
                    "wait",
                    "passive_25",
                    "passive_50",
                    "aggressive_25",
                    "aggressive_50",
                    "aggressive_100",
                ),
                0,
            ),
        },
    ]
    result = _metrics(rows)
    assert result["mean_cost_bps"] == 2.0
    assert result["completion_rate"] == 1.0
    assert result["dropped_observation_rate"] == 0.25


def test_episode_seed_schedule_is_reproducible() -> None:
    assert _paired_seeds(10, 28) == _paired_seeds(10, 28)
    assert _paired_seeds(10, 28) != _paired_seeds(10, 29)


def test_compute_panel_preserves_step30_boundary() -> None:
    panel = _compute_panel(ROOT, (0.025, 0.5))
    assert panel["formal_performance_claim_deferred_to_step30"] is True
    assert panel["budget_feasibility"]["0.025ms"]["imitation_student"] is True
    assert panel["budget_feasibility"]["0.025ms"]["mpc_teacher"] is False


def test_report_artifact_has_required_negative_result() -> None:
    report = json.loads(
        (ROOT / "data/sample/robustness/step28-engineering-matrix/report.json").read_text()
    )
    summary = report["ranking_summary"]
    assert summary["rank_switch_case_count"] > 0
    assert summary["win_counts"]["liquidity_aware"] > summary["win_counts"]["ppo_aggregate"]
    assert report["historical_cells"]["locked_test_opened"] is False


def test_inherited_panels_and_policy_loading() -> None:
    cfg = load_config(CONFIG)
    policies = _load_policies(ROOT, cfg)
    assert set(policies) == {
        "immediate",
        "twap_like",
        "liquidity_aware",
        "ppo_seed_27",
        "ppo_seed_127",
        "ppo_seed_227",
        "ppo_seed_327",
        "ppo_seed_427",
    }
    prediction = _prediction_panel(ROOT)
    queue = _queue_panel(ROOT)
    assert prediction["source_step"] == 25
    assert queue["source_step"] == 16
    assert queue["exact_fifo_reconstructed_historically"] is False


def test_ranking_summary_tracks_switches() -> None:
    cases = (
        StressCase("central_reference", "central", "central"),
        StressCase("stress", "volatility", "shock"),
    )
    seeds = (27, 127, 227, 327, 427)

    def metric(value: float) -> dict[str, object]:
        return {
            "mean_cost_bps": value,
            "median_cost_bps": value,
            "p95_cost_bps": value,
            "cvar95_cost_bps": value,
            "completion_rate": 1.0,
        }

    central = {
        "immediate": metric(4.0),
        "twap_like": metric(3.0),
        "liquidity_aware": metric(1.0),
        **{f"ppo_seed_{seed}": metric(2.0) for seed in seeds},
    }
    stress = {
        "immediate": metric(4.0),
        "twap_like": metric(1.0),
        "liquidity_aware": metric(3.0),
        **{f"ppo_seed_{seed}": metric(2.0) for seed in seeds},
    }
    rows, summary = _ranking_summary({"central_reference": central, "stress": stress}, cases, seeds)
    assert len(rows) == 2
    assert summary["rank_switch_case_count"] == 1
    assert summary["win_counts"]["liquidity_aware"] == 1
    assert summary["win_counts"]["twap_like"] == 1


def test_fast_generator_path_with_stubbed_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rerun = tmp_path / "repo"
    target = rerun / "configs/rl/step27_ppo_engineering.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RL_CONFIG, target)
    cases = (
        StressCase("central_reference", "central", "central"),
        StressCase("stress", "volatility", "shock"),
    )
    seeds = (27, 127, 227, 327, 427)

    def metric(value: float) -> dict[str, object]:
        return {
            "episodes": 2,
            "mean_cost_bps": value,
            "median_cost_bps": value,
            "p95_cost_bps": value,
            "cvar95_cost_bps": value,
            "completion_rate": 1.0,
            "invalid_action_rate": 0.0,
            "dropped_observation_rate": 0.0,
            "delayed_observation_rate": 0.0,
            "action_counts": {},
            "episode_costs_bps": [value, value],
        }

    central = {
        "immediate": metric(4.0),
        "twap_like": metric(3.0),
        "liquidity_aware": metric(1.0),
        **{f"ppo_seed_{seed}": metric(2.0) for seed in seeds},
    }
    stress = {
        "immediate": metric(4.0),
        "twap_like": metric(1.0),
        "liquidity_aware": metric(3.0),
        **{f"ppo_seed_{seed}": metric(2.0) for seed in seeds},
    }
    detail = [
        {
            "case_id": "central_reference",
            "dimension": "central",
            "setting": "central",
            "evidence_class": "synthetic_engineering",
            "policy": "immediate",
            "episodes": 2,
            "mean_cost_bps": 4.0,
            "median_cost_bps": 4.0,
            "p95_cost_bps": 4.0,
            "cvar95_cost_bps": 4.0,
            "completion_rate": 1.0,
            "invalid_action_rate": 0.0,
        }
    ]
    monkeypatch.setattr(robustness_matrix, "stress_cases", lambda: cases)
    monkeypatch.setattr(robustness_matrix, "_load_policies", lambda root, config: {})
    monkeypatch.setattr(
        robustness_matrix,
        "_case_policy_rows",
        lambda *args, **kwargs: (detail, {"central_reference": central, "stress": stress}),
    )
    monkeypatch.setattr(robustness_matrix, "_prediction_panel", lambda root: {"stub": True})
    monkeypatch.setattr(robustness_matrix, "_queue_panel", lambda root: {"stub": True})
    monkeypatch.setattr(
        robustness_matrix, "_compute_panel", lambda root, budgets: {"budgets": list(budgets)}
    )
    report = generate_step28_artifacts(rerun, config_path=CONFIG)
    assert report["interactive_case_count"] == 2
    output = rerun / "data/sample/robustness/step28-engineering-matrix"
    assert (output / "report.json").is_file()
    assert (output / "stress-results.csv").is_file()
    assert (output / "manifest.json").is_file()


def test_full_artifact_regeneration_is_byte_deterministic(tmp_path: Path) -> None:
    rerun = tmp_path / "repo"
    dependencies = [
        CONFIG,
        RL_CONFIG,
        ROOT / "data/sample/analysis/step25-prediction-decision-value/report.json",
        ROOT / "data/sample/queue_models/step16-queue-model-validation/report.json",
        ROOT / "results/validation/step23/inference_benchmark.json",
        ROOT / "results/validation/step26/inference_benchmark.json",
        ROOT / "results/validation/step27/inference_benchmark.json",
    ]
    dependencies.extend(
        ROOT / f"data/sample/rl/step27-ppo-engineering/policy_seed_{seed}.json"
        for seed in (27, 127, 227, 327, 427)
    )
    for source in dependencies:
        relative = source.relative_to(ROOT)
        target = rerun / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    generate_step28_artifacts(rerun)
    expected = ROOT / "data/sample/robustness/step28-engineering-matrix"
    actual = rerun / "data/sample/robustness/step28-engineering-matrix"
    for name in ("report.json", "stress-results.csv", "ranking-stability.json", "manifest.json"):
        assert (actual / name).read_bytes() == (expected / name).read_bytes()
