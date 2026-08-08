"""Step 28 complete registered robustness matrix for the engineering research stack.

The historical research grid remains blocked while Gate C is closed. This module therefore keeps
synthetic engineering, inherited prediction/controller, and blocked historical cells separate.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from robust_execution.rl.ppo import (
    ACTION_LABELS,
    TRAIN_REGIMES,
    Regime,
    RLEngineeringConfig,
    SyntheticExecutionEnv,
    canonical_json,
    greedy_policy,
    immediate_policy,
    liquidity_aware_policy,
    load_policy_artifact,
    reconstruct_reward,
    twap_policy,
)
from robust_execution.rl.ppo import (
    load_config as load_rl_config,
)


class RobustnessError(ValueError):
    """Raised when the Step 28 robustness contract is violated."""


@dataclass(frozen=True)
class Step28Config:
    schema_version: str
    step: int
    research_status: str
    episode_count: int
    seed: int
    ppo_seeds: tuple[int, ...]
    compute_budgets_ms: tuple[float, ...]
    formal_statistics_deferred_to_step29: bool
    formal_performance_deferred_to_step30: bool


@dataclass(frozen=True)
class StressCase:
    case_id: str
    dimension: str
    setting: str
    evidence_class: str = "synthetic_engineering"
    steps_per_episode: int | None = None
    parent_lots: int | None = None
    spread_ticks: int | None = None
    depth_lots: int | None = None
    volatility_ticks: int | None = None
    latency_bps: float | None = None
    fee_bps: float | None = None
    impact_bps: float | None = None
    passive_fill_base: float | None = None
    persistence: float | None = None
    instrument_scale: float = 1.0
    market_time_scale: float = 1.0
    impact_exponent: float = 2.0
    observation_drop_probability: float = 0.0
    observation_delay_steps: int = 0


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path) -> Step28Config:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = Step28Config(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        episode_count=int(raw["episode_count"]),
        seed=int(raw["seed"]),
        ppo_seeds=tuple(int(value) for value in raw["ppo_seeds"]),
        compute_budgets_ms=tuple(float(value) for value in raw["compute_budgets_ms"]),
        formal_statistics_deferred_to_step29=bool(raw["formal_statistics_deferred_to_step29"]),
        formal_performance_deferred_to_step30=bool(raw["formal_performance_deferred_to_step30"]),
    )
    validate_config(config)
    return config


def validate_config(config: Step28Config) -> None:
    if config.schema_version != "robustness-engineering-config-v1" or config.step != 28:
        raise RobustnessError("Step 28 config identity changed")
    if config.research_status != "synthetic_validation_only_non_research":
        raise RobustnessError("Step 28 research boundary changed")
    if config.episode_count < 20:
        raise RobustnessError("Step 28 requires at least twenty paired episodes per cell")
    if len(config.ppo_seeds) < 5 or len(set(config.ppo_seeds)) != len(config.ppo_seeds):
        raise RobustnessError("Step 28 requires at least five unique PPO seeds")
    if tuple(sorted(set(config.compute_budgets_ms))) != config.compute_budgets_ms:
        raise RobustnessError("compute budgets must be sorted and unique")
    if not config.compute_budgets_ms or config.compute_budgets_ms[0] <= 0:
        raise RobustnessError("compute budgets must be positive")
    if not config.formal_statistics_deferred_to_step29:
        raise RobustnessError("Step 28 may not perform the Step 29 confirmatory analysis")
    if not config.formal_performance_deferred_to_step30:
        raise RobustnessError("Step 28 may not promote engineering timings to performance claims")


def _base_regime() -> Regime:
    return TRAIN_REGIMES[1]


def stress_cases() -> tuple[StressCase, ...]:
    base = _base_regime()
    return (
        StressCase("central_reference", "central", "step27_active_training_regime"),
        StressCase("latency_zero", "latency", "zero", latency_bps=0.0),
        StressCase("latency_half", "latency", "0.5x", latency_bps=0.5 * base.latency_bps),
        StressCase("latency_2x", "latency", "2x", latency_bps=2.0 * base.latency_bps),
        StressCase("latency_5x", "latency", "5x", latency_bps=5.0 * base.latency_bps),
        StressCase("grid_10ms_proxy", "decision_grid", "10ms_proxy", steps_per_episode=24),
        StressCase("grid_100ms_proxy", "decision_grid", "100ms_proxy", steps_per_episode=10),
        StressCase("grid_250ms_proxy", "decision_grid", "250ms_proxy", steps_per_episode=8),
        StressCase("grid_1000ms_proxy", "decision_grid", "1000ms_proxy", steps_per_episode=6),
        StressCase("liquidity_high", "liquidity", "high", depth_lots=180),
        StressCase("liquidity_low", "liquidity", "low", depth_lots=70),
        StressCase("liquidity_adversarial_thin", "liquidity", "adversarial_thin", depth_lots=30),
        StressCase("spread_narrow", "spread", "narrow", spread_ticks=2),
        StressCase("spread_wide", "spread", "wide", spread_ticks=8),
        StressCase("spread_adversarial", "spread", "adversarial_wide", spread_ticks=12),
        StressCase("volatility_low", "volatility", "low", volatility_ticks=1),
        StressCase("volatility_high", "volatility", "high", volatility_ticks=4),
        StressCase("volatility_shock", "volatility", "shock", volatility_ticks=8),
        StressCase("queue_optimistic", "queue", "optimistic_proxy", passive_fill_base=0.78),
        StressCase("queue_pessimistic", "queue", "pessimistic_proxy", passive_fill_base=0.25),
        StressCase(
            "queue_cancellation_perturb",
            "queue",
            "cancellation_allocation_proxy",
            passive_fill_base=0.40,
        ),
        StressCase("fees_zero", "fees_rebates", "zero", fee_bps=0.0),
        StressCase("fees_favourable", "fees_rebates", "favourable", fee_bps=0.05),
        StressCase("fees_adverse", "fees_rebates", "adverse", fee_bps=1.0),
        StressCase("size_10pct_depth", "parent_size", "10pct_depth_proxy", parent_lots=10),
        StressCase("size_25pct_depth", "parent_size", "25pct_depth_proxy", parent_lots=25),
        StressCase("size_50pct_depth", "parent_size", "50pct_depth_proxy", parent_lots=50),
        StressCase("horizon_30s_proxy", "horizon", "30s_proxy", market_time_scale=0.5),
        StressCase("horizon_300s_proxy", "horizon", "300s_proxy", market_time_scale=5.0),
        StressCase("impact_half", "impact", "0.5x_coefficient", impact_bps=0.5 * base.impact_bps),
        StressCase("impact_2x", "impact", "2x_coefficient", impact_bps=2.0 * base.impact_bps),
        StressCase("impact_linear", "impact", "linear_form_misspecification", impact_exponent=1.0),
        StressCase("impact_cubic", "impact", "cubic_form_misspecification", impact_exponent=3.0),
        StressCase(
            "data_drop_10pct",
            "data_quality",
            "dropped_updates_10pct",
            observation_drop_probability=0.10,
        ),
        StressCase(
            "data_drop_30pct",
            "data_quality",
            "dropped_updates_30pct",
            observation_drop_probability=0.30,
        ),
        StressCase(
            "data_delay_1",
            "data_quality",
            "one_decision_delay",
            observation_delay_steps=1,
        ),
        StressCase(
            "data_delay_2",
            "data_quality",
            "two_decision_delay",
            observation_delay_steps=2,
        ),
        StressCase(
            "distribution_later_proxy",
            "distribution",
            "later_regime_proxy",
            persistence=0.90,
        ),
        StressCase(
            "distribution_instrument_low",
            "distribution",
            "second_instrument_scale_0.70",
            instrument_scale=0.70,
        ),
        StressCase(
            "distribution_instrument_high",
            "distribution",
            "second_instrument_scale_1.35",
            instrument_scale=1.35,
        ),
        StressCase(
            "distribution_unseen_combined",
            "distribution",
            "unseen_combined_regime",
            evidence_class="adversarial_synthetic",
            spread_ticks=8,
            depth_lots=35,
            volatility_ticks=6,
            latency_bps=1.5,
            fee_bps=1.2,
            impact_bps=2.0,
            passive_fill_base=0.22,
            persistence=0.15,
        ),
        StressCase(
            "simulator_mismatch_adverse",
            "simulator_mismatch",
            "queue_impact_resilience_shift",
            evidence_class="adversarial_synthetic",
            depth_lots=55,
            impact_bps=1.5,
            passive_fill_base=0.20,
            persistence=0.75,
            market_time_scale=1.5,
            impact_exponent=1.5,
        ),
        StressCase(
            "simulator_mismatch_form",
            "simulator_mismatch",
            "impact_form_and_fill_shift",
            evidence_class="adversarial_synthetic",
            depth_lots=80,
            passive_fill_base=0.70,
            impact_exponent=1.0,
        ),
    )


def _regime_for_case(case: StressCase) -> Regime:
    base = _base_regime()
    return replace(
        base,
        name=f"step28_{case.case_id}",
        spread_ticks=case.spread_ticks if case.spread_ticks is not None else base.spread_ticks,
        depth_lots=case.depth_lots if case.depth_lots is not None else base.depth_lots,
        volatility_ticks=(
            case.volatility_ticks if case.volatility_ticks is not None else base.volatility_ticks
        ),
        latency_bps=case.latency_bps if case.latency_bps is not None else base.latency_bps,
        fee_bps=case.fee_bps if case.fee_bps is not None else base.fee_bps,
        impact_bps=case.impact_bps if case.impact_bps is not None else base.impact_bps,
        passive_fill_base=(
            case.passive_fill_base if case.passive_fill_base is not None else base.passive_fill_base
        ),
        persistence=case.persistence if case.persistence is not None else base.persistence,
    )


def _rl_config_for_case(base: RLEngineeringConfig, case: StressCase) -> RLEngineeringConfig:
    return replace(
        base,
        steps_per_episode=(
            case.steps_per_episode if case.steps_per_episode is not None else base.steps_per_episode
        ),
        parent_lots=case.parent_lots if case.parent_lots is not None else base.parent_lots,
    )


def _corruption_seed(case: StressCase, episode_seed: int) -> int:
    material = f"{case.case_id}:{episode_seed}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def run_stress_episode(
    base_config: RLEngineeringConfig,
    *,
    case: StressCase,
    episode_seed: int,
    policy: Callable[[np.ndarray, np.ndarray], int],
) -> dict[str, object]:
    config = _rl_config_for_case(base_config, case)
    env = SyntheticExecutionEnv(
        config,
        regime=_regime_for_case(case),
        seed=episode_seed,
        instrument_scale=case.instrument_scale,
        market_time_scale=case.market_time_scale,
        impact_exponent=case.impact_exponent,
    )
    observation = env.reset()
    history: list[np.ndarray] = []
    last_delivered = observation.copy()
    dropped = 0
    delayed = 0
    invalid = 0
    actions = dict.fromkeys(ACTION_LABELS, 0)
    corruption_rng = np.random.default_rng(_corruption_seed(case, episode_seed))
    done = False
    while not done:
        history.append(observation.copy())
        delivered = observation
        if case.observation_delay_steps:
            source = max(0, len(history) - 1 - case.observation_delay_steps)
            delivered = history[source]
            delayed += int(source != len(history) - 1)
        if case.observation_drop_probability > 0:
            if float(corruption_rng.random()) < case.observation_drop_probability:
                delivered = last_delivered
                dropped += 1
            else:
                last_delivered = delivered.copy()
        else:
            last_delivered = delivered.copy()
        mask = env.valid_action_mask()
        action = int(policy(delivered, mask))
        if not 0 <= action < len(ACTION_LABELS):
            raise RobustnessError("policy emitted an action outside the Step 27 action space")
        observation, _, done, info = env.step(action)
        invalid += int(bool(info["invalid"]))
        actions[ACTION_LABELS[action]] += 1
    for row in env.episode_log:
        if not math.isclose(float(row["reward"]), reconstruct_reward(row), abs_tol=1e-10):
            raise RobustnessError("Step 28 reward reconstruction failed")
    return {
        "cost_bps": float(env.cumulative_cost_bps),
        "completed": bool(env.state.remaining_lots == 0),
        "steps": len(env.episode_log),
        "invalid_actions": invalid,
        "dropped_observations": dropped,
        "delayed_observations": delayed,
        "actions": actions,
    }


def _metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    costs = np.asarray([float(row["cost_bps"]) for row in rows], dtype=float)
    threshold = float(np.quantile(costs, 0.95))
    steps = sum(int(row["steps"]) for row in rows)
    action_totals = dict.fromkeys(ACTION_LABELS, 0)
    for row in rows:
        for label, count in dict(row["actions"]).items():
            action_totals[str(label)] += int(count)
    return {
        "episodes": len(rows),
        "mean_cost_bps": float(costs.mean()),
        "median_cost_bps": float(np.median(costs)),
        "p95_cost_bps": threshold,
        "cvar95_cost_bps": float(costs[costs >= threshold].mean()),
        "completion_rate": float(np.mean([bool(row["completed"]) for row in rows])),
        "invalid_action_rate": float(
            sum(int(row["invalid_actions"]) for row in rows) / max(1, steps)
        ),
        "dropped_observation_rate": float(
            sum(int(row["dropped_observations"]) for row in rows) / max(1, steps)
        ),
        "delayed_observation_rate": float(
            sum(int(row["delayed_observations"]) for row in rows) / max(1, steps)
        ),
        "action_counts": action_totals,
        "episode_costs_bps": [float(value) for value in costs],
    }


def _paired_seeds(count: int, seed: int) -> tuple[int, ...]:
    rng = np.random.default_rng(seed)
    return tuple(int(value) for value in rng.integers(0, 2**31 - 1, size=count))


def _load_policies(
    root: Path, config: Step28Config
) -> dict[str, Callable[[np.ndarray, np.ndarray], int]]:
    policies: dict[str, Callable[[np.ndarray, np.ndarray], int]] = {
        "immediate": immediate_policy,
        "twap_like": twap_policy,
        "liquidity_aware": liquidity_aware_policy,
    }
    policy_root = root / "data/sample/rl/step27-ppo-engineering"
    for seed in config.ppo_seeds:
        path = policy_root / f"policy_seed_{seed}.json"
        model = load_policy_artifact(json.loads(path.read_text(encoding="utf-8")))
        policies[f"ppo_seed_{seed}"] = greedy_policy(model)
    return policies


def _case_policy_rows(
    base_config: RLEngineeringConfig,
    *,
    cases: Iterable[StressCase],
    policies: dict[str, Callable[[np.ndarray, np.ndarray], int]],
    episode_seeds: tuple[int, ...],
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    detail_rows: list[dict[str, object]] = []
    metrics_by_case: dict[str, dict[str, object]] = {}
    for case in cases:
        metrics_by_case[case.case_id] = {}
        for policy_name, policy in policies.items():
            episodes = [
                run_stress_episode(
                    base_config,
                    case=case,
                    episode_seed=episode_seed,
                    policy=policy,
                )
                for episode_seed in episode_seeds
            ]
            metrics = _metrics(episodes)
            metrics_by_case[case.case_id][policy_name] = metrics
            detail_rows.append(
                {
                    "case_id": case.case_id,
                    "dimension": case.dimension,
                    "setting": case.setting,
                    "evidence_class": case.evidence_class,
                    "policy": policy_name,
                    "episodes": metrics["episodes"],
                    "mean_cost_bps": metrics["mean_cost_bps"],
                    "median_cost_bps": metrics["median_cost_bps"],
                    "p95_cost_bps": metrics["p95_cost_bps"],
                    "cvar95_cost_bps": metrics["cvar95_cost_bps"],
                    "completion_rate": metrics["completion_rate"],
                    "invalid_action_rate": metrics["invalid_action_rate"],
                }
            )
    return detail_rows, metrics_by_case


def _ppo_family(metrics: dict[str, object], seeds: tuple[int, ...]) -> dict[str, object]:
    seed_metrics = [metrics[f"ppo_seed_{seed}"] for seed in seeds]
    keys = ("mean_cost_bps", "median_cost_bps", "p95_cost_bps", "cvar95_cost_bps")
    output = {key: float(np.mean([float(row[key]) for row in seed_metrics])) for key in keys}
    output["completion_rate"] = float(
        np.mean([float(row["completion_rate"]) for row in seed_metrics])
    )
    output["seed_count"] = len(seed_metrics)
    return output


def _ranking_summary(
    metrics_by_case: dict[str, dict[str, object]],
    cases: tuple[StressCase, ...],
    seeds: tuple[int, ...],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    ranking_rows: list[dict[str, object]] = []
    win_counts = dict.fromkeys(("ppo_aggregate", "immediate", "twap_like", "liquidity_aware"), 0)
    central: dict[str, float] = {}
    for case in cases:
        metrics = metrics_by_case[case.case_id]
        family = {
            "ppo_aggregate": _ppo_family(metrics, seeds),
            "immediate": metrics["immediate"],
            "twap_like": metrics["twap_like"],
            "liquidity_aware": metrics["liquidity_aware"],
        }
        ordered = sorted(family, key=lambda name: (float(family[name]["mean_cost_bps"]), name))
        win_counts[ordered[0]] += 1
        if case.case_id == "central_reference":
            central = {name: float(row["mean_cost_bps"]) for name, row in family.items()}
        ranking_rows.append(
            {
                "case_id": case.case_id,
                "dimension": case.dimension,
                "setting": case.setting,
                "ranking_best_to_worst": ordered,
                "mean_cost_bps": {name: float(family[name]["mean_cost_bps"]) for name in family},
            }
        )
    if not central:
        raise RobustnessError("central robustness reference is missing")
    rank_switches = sum(
        row["ranking_best_to_worst"]
        != next(
            item["ranking_best_to_worst"]
            for item in ranking_rows
            if item["case_id"] == "central_reference"
        )
        for row in ranking_rows
        if row["case_id"] != "central_reference"
    )
    worst_deltas: dict[str, float] = dict.fromkeys(central, -math.inf)
    for row in ranking_rows:
        for name, value in dict(row["mean_cost_bps"]).items():
            worst_deltas[name] = max(worst_deltas[name], float(value) - central[name])
    return ranking_rows, {
        "win_counts": win_counts,
        "rank_switch_case_count": rank_switches,
        "noncentral_case_count": len(ranking_rows) - 1,
        "worst_mean_cost_increase_vs_central_bps": worst_deltas,
    }


def _prediction_panel(root: Path) -> dict[str, object]:
    path = root / "data/sample/analysis/step25-prediction-decision-value/report.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    payload = value["payload"]
    modes = (
        "calibrated_model",
        "uncalibrated_model",
        "stale",
        "training_base_rate",
        "shuffled_within_day_instrument",
    )
    horizons: dict[str, object] = {}
    for horizon in payload["candidate_horizons"]:
        metrics = payload["prediction_analysis"][horizon]["metrics"]
        decisions = payload["decision_sensitivity"]["horizons"][horizon]
        horizons[horizon] = {
            name: {
                "log_loss": float(metrics[name]["log_loss"]),
                "brier": float(metrics[name]["brier"]),
                "first_grid_weight_with_action_change_bps": decisions[name][
                    "first_grid_weight_with_action_change_bps"
                ],
            }
            for name in modes
        }
    return {
        "source_step": 25,
        "source_sha256": sha256_path(path),
        "required_modes_covered": list(modes),
        "perfect_event_oracle_retained_as_upper_bound_not_degradation": True,
        "horizons": horizons,
    }


def _queue_panel(root: Path) -> dict[str, object]:
    path = root / "data/sample/queue_models/step16-queue-model-validation/report.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    return {
        "source_step": 16,
        "source_sha256": sha256_path(path),
        "exact_fifo_reconstructed_historically": False,
        "required_assumptions": ["optimistic", "central", "pessimistic"],
        "engineering_proxy_also_executed_in_step28": True,
        "step16_report_schema": value.get("schema_version"),
    }


def _compute_panel(root: Path, budgets_ms: tuple[float, ...]) -> dict[str, object]:
    step23_path = root / "results/validation/step23/inference_benchmark.json"
    step26_path = root / "results/validation/step26/inference_benchmark.json"
    step27_path = root / "results/validation/step27/inference_benchmark.json"
    step23 = json.loads(step23_path.read_text(encoding="utf-8"))
    step26 = json.loads(step26_path.read_text(encoding="utf-8"))
    step27 = json.loads(step27_path.read_text(encoding="utf-8"))
    components: dict[str, float] = {}
    for horizon, row in step23["models"].items():
        components[f"temporal_{horizon}"] = float(row["p95_ns"]) / 1_000_000.0
    components["imitation_student"] = (
        float(step26["student_numpy_batch_one"]["p95_ns"]) / 1_000_000.0
    )
    components["mpc_teacher"] = float(step26["teacher_cpp_shared_mpc"]["p95_ns"]) / 1_000_000.0
    for seed, row in step27["policies"].items():
        components[f"ppo_seed_{seed}"] = float(row["p95_ns"]) / 1_000_000.0
    feasibility = {
        f"{budget:g}ms": {
            name: bool(latency <= budget) for name, latency in sorted(components.items())
        }
        for budget in budgets_ms
    }
    return {
        "status": "engineering_machine_specific_not_step30_performance_claim",
        "p95_ms": components,
        "budgets_ms": list(budgets_ms),
        "budget_feasibility": feasibility,
        "formal_performance_claim_deferred_to_step30": True,
        "source_sha256": {
            "step23": sha256_path(step23_path),
            "step26": sha256_path(step26_path),
            "step27": sha256_path(step27_path),
        },
    }


def _dimension_registry() -> dict[str, object]:
    return {
        "latency": {
            "research_required": "zero, 0.5x, 1x, 2x, 5x central plus absolute checks",
            "engineering_status": (
                "multipliers_executed_absolute_ms_deferred_until_calibrated_latency"
            ),
        },
        "decision_grid": {
            "research_required_ms": [10, 50, 100, 250, 1000],
            "engineering_status": "normalized_decision_opportunity_proxies_executed",
        },
        "liquidity": {"engineering_status": "low_high_and_adversarial_thin_executed"},
        "spread": {"engineering_status": "narrow_wide_and_adversarial_wide_executed"},
        "volatility": {"engineering_status": "low_high_and_shock_executed"},
        "queue": {
            "engineering_status": "step16_exact_scenarios_plus_step28_fill_assumption_proxies",
            "historical_central_calibration": "blocked_gate_c",
        },
        "fees_rebates": {"engineering_status": "zero_favourable_and_adverse_executed"},
        "parent_size": {
            "research_required_depth_fraction": [0.10, 0.25, 0.50, 1.00],
            "engineering_status": "all_four_registered_with_100pct_as_step27_central_reference",
        },
        "horizon": {
            "research_required_seconds": [30, 60, 300],
            "engineering_status": "market_time_scale_proxies_executed",
        },
        "impact": {
            "engineering_status": "coefficient_and_functional_form_misspecification_executed"
        },
        "prediction": {
            "engineering_status": "required_modes_inherited_and_revalidated_from_step25"
        },
        "data_quality": {"engineering_status": "dropped_and_delayed_observation_updates_executed"},
        "distribution": {
            "engineering_status": (
                "temporal_instrument_and_unseen_combined_synthetic_shifts_executed"
            ),
            "historical_later_dates_and_second_real_instrument": "blocked_gate_c",
        },
        "compute": {
            "engineering_status": "existing_p95_timings_checked_against_budget_grid",
            "formal_latency_injection_and_cpu_gpu_claims": "deferred_step30",
        },
        "simulator_mismatch": {
            "engineering_status": (
                "joint_queue_impact_resilience_and_functional_form_shifts_executed"
            )
        },
    }


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    if not rows:
        raise RobustnessError("cannot serialize an empty Step 28 table")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def generate_step28_artifacts(root: Path, *, config_path: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    config_path = config_path or root / "configs/robustness/step28_robustness_engineering.json"
    config = load_config(config_path)
    rl_config = load_rl_config(root / "configs/rl/step27_ppo_engineering.json")
    if tuple(rl_config.training_seeds) != config.ppo_seeds:
        raise RobustnessError("Step 28 PPO seeds do not match Step 27 registered policies")
    cases = stress_cases()
    if len({case.case_id for case in cases}) != len(cases):
        raise RobustnessError("Step 28 stress-case ids must be unique")
    policies = _load_policies(root, config)
    episode_seeds = _paired_seeds(config.episode_count, config.seed)
    detail_rows, metrics_by_case = _case_policy_rows(
        rl_config,
        cases=cases,
        policies=policies,
        episode_seeds=episode_seeds,
    )
    ranking_rows, ranking_summary = _ranking_summary(
        metrics_by_case,
        cases,
        config.ppo_seeds,
    )
    report = {
        "schema_version": "robustness-engineering-report-v1",
        "step": 28,
        "research_status": config.research_status,
        "gate_c_status": "blocked_no_admitted_historical_research_dataset",
        "gate_i_status": "pending_step29_statistics_and_historical_activation",
        "paired_episode_count_per_cell": config.episode_count,
        "paired_episode_seed_sha256": hashlib.sha256(
            canonical_json(list(episode_seeds)).encode()
        ).hexdigest(),
        "competitive_policy_families": [
            "ppo_aggregate_five_seeds",
            "immediate",
            "twap_like",
            "liquidity_aware",
        ],
        "ppo_seed_policies": [f"ppo_seed_{seed}" for seed in config.ppo_seeds],
        "sanity_policies_not_ranked_here": ["random", "wait_noop"],
        "dimension_registry": _dimension_registry(),
        "interactive_case_count": len(cases),
        "interactive_cases": [
            {
                "case_id": case.case_id,
                "dimension": case.dimension,
                "setting": case.setting,
                "evidence_class": case.evidence_class,
            }
            for case in cases
        ],
        "interactive_metrics": metrics_by_case,
        "ranking_rows": ranking_rows,
        "ranking_summary": ranking_summary,
        "prediction_panel": _prediction_panel(root),
        "queue_panel": _queue_panel(root),
        "compute_panel": _compute_panel(root, config.compute_budgets_ms),
        "historical_cells": {
            "status": "blocked_gate_c",
            "locked_test_opened": False,
            "historical_queue_calibration_performed": False,
            "later_real_dates_tested": False,
            "second_real_instrument_tested": False,
            "claim": "no_historical_robustness_result",
        },
        "statistics_boundary": {
            "paired_rows_preserved": True,
            "formal_confidence_intervals": False,
            "multiplicity_adjustment": False,
            "dependence_aware_bootstrap": False,
            "deferred_to_step29": True,
        },
        "performance_boundary": {
            "formal_performance_claim": False,
            "cpu_gpu_comparison": False,
            "compiled_inference_claim": False,
            "deferred_to_step30": True,
        },
        "scientific_boundary": [
            "synthetic engineering and adversarial evidence only",
            "historical cells remain blocked by Gate C",
            "no Step 29 confidence or multiplicity claim",
            "no Step 30 hardware-performance claim",
            "no final strategy ranking selected from engineering stresses",
        ],
    }
    output_dir = root / "data/sample/robustness/step28-engineering-matrix"
    result_dir = root / "results/validation/step28"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    report_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
    detail_path = output_dir / "stress-results.csv"
    detail_path.write_bytes(_csv_bytes(detail_rows))
    ranking_path = output_dir / "ranking-stability.json"
    ranking_path.write_text(
        canonical_json({"rows": ranking_rows, "summary": ranking_summary}) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "robustness-engineering-manifest-v1",
        "step": 28,
        "research_status": config.research_status,
        "files": {
            "report.json": sha256_path(report_path),
            "stress-results.csv": sha256_path(detail_path),
            "ranking-stability.json": sha256_path(ranking_path),
        },
        "config_sha256": sha256_path(config_path),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    (result_dir / "artifact_hashes.json").write_text(
        canonical_json(
            {
                "report_sha256": sha256_path(report_path),
                "stress_results_sha256": sha256_path(detail_path),
                "ranking_stability_sha256": sha256_path(ranking_path),
                "manifest_sha256": sha256_path(manifest_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return report
