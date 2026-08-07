from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from robust_execution.rl.ppo import (
    ACTION_INDEX,
    ACTION_LABELS,
    OOD_REGIMES,
    TRAIN_REGIMES,
    ActorCritic,
    RLEngineeringConfig,
    RLEngineeringError,
    SyntheticExecutionEnv,
    canonical_json,
    evaluate_policy,
    generate_step27_artifacts,
    greedy_policy,
    historical_zero_shot_gate,
    immediate_policy,
    load_config,
    load_policy_artifact,
    random_policy,
    reconstruct_reward,
    run_policy_episode,
    train_seed,
    validate_config,
    wait_policy,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/rl/step27_ppo_engineering.json"


def config() -> RLEngineeringConfig:
    return load_config(CONFIG_PATH)


def tiny_config() -> RLEngineeringConfig:
    base = config()
    return RLEngineeringConfig(
        **{
            **base.__dict__,
            "training_seeds": (27, 127, 227, 327, 427),
            "train_episodes_per_update": 4,
            "updates": 2,
            "evaluation_episodes": 10,
            "ood_episodes": 10,
        }
    )


def test_config_contract_and_failures() -> None:
    cfg = config()
    assert cfg.algorithm == "categorical_ppo"
    assert len(cfg.training_seeds) == 5
    with pytest.raises(RLEngineeringError):
        validate_config(RLEngineeringConfig(**{**cfg.__dict__, "step": 26}))
    with pytest.raises(RLEngineeringError):
        validate_config(RLEngineeringConfig(**{**cfg.__dict__, "training_seeds": (1, 2)}))
    with pytest.raises(RLEngineeringError):
        validate_config(RLEngineeringConfig(**{**cfg.__dict__, "gamma": 0.0}))
    with pytest.raises(RLEngineeringError):
        validate_config(RLEngineeringConfig(**{**cfg.__dict__, "hidden_units": 2}))


def test_environment_is_deterministic_and_future_rng_is_not_observed() -> None:
    cfg = config()
    left = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[0], seed=55)
    right = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[0], seed=55)
    assert np.array_equal(left.reset(), right.reset())
    before = left.observation().copy()
    left._rng.random(100)  # mutate only unseen future randomness
    assert np.array_equal(before, left.observation())


def test_action_mask_and_terminal_completion() -> None:
    cfg = config()
    env = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[0], seed=66)
    env.reset()
    for _ in range(cfg.steps_per_episode - 1):
        _, _, done, _ = env.step(ACTION_INDEX["wait"])
        assert not done
    mask = env.valid_action_mask()
    assert not mask[ACTION_INDEX["wait"]]
    assert not mask[ACTION_INDEX["passive_25"]]
    _, _, done, info = env.step(ACTION_INDEX["wait"])
    assert done
    assert info["invalid"] is True
    assert info["completed"] is True
    assert env.state.remaining_lots == 0
    assert info["executed_lots"] == cfg.parent_lots
    assert float(info["invalid_action_penalty_bps"]) == cfg.invalid_action_penalty_bps


def test_reward_components_reconstruct_exactly() -> None:
    cfg = config()
    env = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[1], seed=77)
    env.reset()
    _, reward, _, info = env.step(ACTION_INDEX["aggressive_25"])
    assert math.isclose(reward, reconstruct_reward(info), abs_tol=1e-12)
    assert float(info["execution_cost_bps"]) != 0.0
    assert float(info["inventory_risk_bps"]) > 0.0


def test_bad_actions_and_lifecycle_fail_closed() -> None:
    cfg = config()
    env = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[0], seed=88)
    with pytest.raises(RLEngineeringError):
        env.observation()
    env.reset()
    with pytest.raises(RLEngineeringError):
        env.step(-1)
    with pytest.raises(RLEngineeringError):
        env.step(len(ACTION_LABELS))
    run_policy_episode(
        cfg,
        regime=TRAIN_REGIMES[0],
        seed=89,
        policy=immediate_policy,
    )
    env2 = SyntheticExecutionEnv(cfg, regime=TRAIN_REGIMES[0], seed=89)
    env2.reset()
    env2.step(ACTION_INDEX["aggressive_100"])
    with pytest.raises(RLEngineeringError):
        env2.step(ACTION_INDEX["wait"])


def test_sanity_policies_complete_and_noop_is_costly() -> None:
    cfg = config()
    specs = [(TRAIN_REGIMES[i % len(TRAIN_REGIMES)], 100 + i, 1.0) for i in range(12)]
    immediate = evaluate_policy(cfg, policy=immediate_policy, specs=specs)
    noop = evaluate_policy(cfg, policy=wait_policy, specs=specs)
    random = evaluate_policy(
        cfg,
        policy=random_policy(np.random.default_rng(101)),
        specs=specs,
    )
    assert immediate["completion_rate"] == 1.0
    assert noop["completion_rate"] == 1.0
    assert random["completion_rate"] == 1.0
    assert float(noop["mean_cost_bps"]) > float(immediate["mean_cost_bps"])


def test_ppo_training_is_seed_deterministic() -> None:
    cfg = tiny_config()
    first, first_history = train_seed(cfg, 27)
    second, second_history = train_seed(cfg, 27)
    assert first_history == second_history
    for left, right in zip(first.state_dict().values(), second.state_dict().values(), strict=True):
        assert torch.equal(left, right)


def test_policy_artifact_round_trip_and_tamper_rejection(tmp_path: Path) -> None:
    cfg = tiny_config()
    model, _ = train_seed(cfg, 127)
    payload = {
        "schema_version": "rl-policy-artifact-v1",
        "step": 27,
        "research_status": cfg.research_status,
        "algorithm": cfg.algorithm,
        "seed": 127,
        "state_features": [
            "remaining_fraction",
            "time_remaining_fraction",
            "spread_ticks_scaled",
            "depth_ratio",
            "imbalance",
            "volatility_scaled",
            "latency_scaled",
            "fee_scaled",
            "impact_scaled",
            "recent_fill_fraction",
            "adverse_momentum_scaled",
        ],
        "action_labels": list(ACTION_LABELS),
        "hidden_units": cfg.hidden_units,
        "state_dict": {
            name: tensor.detach().cpu().numpy().tolist()
            for name, tensor in sorted(model.state_dict().items())
        },
    }
    restored = load_policy_artifact(json.loads(canonical_json(payload)))
    observation = np.zeros(11, dtype=np.float32)
    mask = np.ones(len(ACTION_LABELS), dtype=bool)
    assert greedy_policy(model)(observation, mask) == greedy_policy(restored)(observation, mask)
    broken = json.loads(canonical_json(payload))
    broken["action_labels"] = list(reversed(ACTION_LABELS))
    with pytest.raises(RLEngineeringError):
        load_policy_artifact(broken)
    broken = json.loads(canonical_json(payload))
    broken["state_dict"].pop(next(iter(broken["state_dict"])))
    with pytest.raises(RLEngineeringError):
        load_policy_artifact(broken)


def test_ood_environment_changes_cost_surface() -> None:
    cfg = config()
    id_result = run_policy_episode(
        cfg,
        regime=TRAIN_REGIMES[0],
        seed=111,
        policy=immediate_policy,
    )
    ood_result = run_policy_episode(
        cfg,
        regime=OOD_REGIMES[-1],
        seed=111,
        policy=immediate_policy,
        instrument_scale=1.35,
    )
    assert float(ood_result["cost_bps"]) > float(id_result["cost_bps"])


def test_full_artifact_regeneration_is_byte_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tiny_config()
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        canonical_json(
            {
                **cfg.__dict__,
                "training_seeds": list(cfg.training_seeds),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Redirect the output paths while keeping the generator's repository-relative contract.
    fake_root = tmp_path / "repo"
    (fake_root / "configs/rl").mkdir(parents=True)
    (fake_root / "configs/rl/step27_ppo_engineering.json").write_bytes(cfg_path.read_bytes())
    generate_step27_artifacts(fake_root)
    first = (fake_root / "data/sample/rl/step27-ppo-engineering/report.json").read_bytes()
    generate_step27_artifacts(fake_root)
    second = (fake_root / "data/sample/rl/step27-ppo-engineering/report.json").read_bytes()
    assert first == second


def test_historical_zero_shot_gate_blocks_current_state_and_fine_tuning() -> None:
    with pytest.raises(RLEngineeringError):
        historical_zero_shot_gate(admitted_days_per_instrument=0, fine_tune_requested=False)
    with pytest.raises(RLEngineeringError):
        historical_zero_shot_gate(admitted_days_per_instrument=100, fine_tune_requested=True)
    assert (
        historical_zero_shot_gate(admitted_days_per_instrument=100, fine_tune_requested=False)
        == "eligible_zero_shot_only"
    )
