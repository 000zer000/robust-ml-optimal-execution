"""Step 29 dependence-aware statistical inference.

The locked historical Tier-1 analysis remains blocked while Gate C is closed.  The committed
artifacts therefore validate the frozen methods on the Step 28 synthetic engineering matrix and
keep all confirmatory historical fields explicitly unresolved.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np


class StatisticalError(ValueError):
    """Raised when the Step 29 statistical contract is violated."""


@dataclass(frozen=True)
class Step29Config:
    schema_version: str
    step: int
    research_status: str
    bootstrap_repetitions: int
    ranking_bootstrap_repetitions: int
    seed: int
    alpha: float
    min_block_length: int
    max_block_length: int
    acf_threshold: float
    comparator: str
    challenger_policies: tuple[str, ...]
    historical_confirmatory_analysis_blocked: bool


@dataclass(frozen=True)
class PairedHistoricalRow:
    instrument: str
    side: str
    size_bucket: str
    day: str
    policy_cost_bps: float
    comparator_cost_bps: float
    policy_completion: float = 1.0
    comparator_completion: float = 1.0


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path) -> Step29Config:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = Step29Config(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        bootstrap_repetitions=int(raw["bootstrap_repetitions"]),
        ranking_bootstrap_repetitions=int(raw["ranking_bootstrap_repetitions"]),
        seed=int(raw["seed"]),
        alpha=float(raw["alpha"]),
        min_block_length=int(raw["min_block_length"]),
        max_block_length=int(raw["max_block_length"]),
        acf_threshold=float(raw["acf_threshold"]),
        comparator=str(raw["comparator"]),
        challenger_policies=tuple(str(x) for x in raw["challenger_policies"]),
        historical_confirmatory_analysis_blocked=bool(
            raw["historical_confirmatory_analysis_blocked"]
        ),
    )
    validate_config(config)
    return config


def validate_config(config: Step29Config) -> None:
    if config.schema_version != "statistics-engineering-config-v1" or config.step != 29:
        raise StatisticalError("Step 29 config identity changed")
    if config.research_status != "synthetic_validation_only_non_research":
        raise StatisticalError("Step 29 research boundary changed")
    if config.bootstrap_repetitions < 1000 or config.ranking_bootstrap_repetitions < 1000:
        raise StatisticalError("Step 29 requires at least 1000 bootstrap repetitions")
    if not 0.0 < config.alpha < 0.5:
        raise StatisticalError("alpha must be in (0, 0.5)")
    if not 2 <= config.min_block_length <= config.max_block_length <= 7:
        raise StatisticalError("frozen block-length bounds changed")
    if not 0.0 < config.acf_threshold < 1.0:
        raise StatisticalError("invalid autocorrelation threshold")
    if len(config.challenger_policies) != len(set(config.challenger_policies)):
        raise StatisticalError("challenger policies must be unique")
    if config.comparator in config.challenger_policies:
        raise StatisticalError("comparator may not be a challenger")
    if not config.historical_confirmatory_analysis_blocked:
        raise StatisticalError("Gate C is closed; historical confirmatory analysis must be blocked")


def autocorrelation(values: Sequence[float], lag: int) -> float:
    x = np.asarray(values, dtype=float)
    if lag <= 0 or lag >= len(x):
        raise StatisticalError("autocorrelation lag out of range")
    left, right = x[:-lag], x[lag:]
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def select_block_length(
    values: Sequence[float], *, threshold: float, minimum: int, maximum: int
) -> tuple[int, dict[str, float]]:
    if len(values) < maximum + 2:
        raise StatisticalError("insufficient ordered pseudo-days for block-length selection")
    acf = {str(lag): autocorrelation(values, lag) for lag in range(1, maximum + 2)}
    selected = maximum
    for lag in range(1, maximum + 1):
        if abs(acf[str(lag)]) < threshold and abs(acf[str(lag + 1)]) < threshold:
            selected = lag
            break
    return max(minimum, min(maximum, selected)), acf


def moving_block_indices(n: int, block_length: int, repetitions: int, seed: int) -> np.ndarray:
    if n <= 0 or not 1 <= block_length <= n or repetitions <= 0:
        raise StatisticalError("invalid moving-block bootstrap dimensions")
    rng = np.random.default_rng(seed)
    blocks = math.ceil(n / block_length)
    starts = rng.integers(0, n, size=(repetitions, blocks))
    offsets = np.arange(block_length)
    indices = (starts[..., None] + offsets) % n
    return indices.reshape(repetitions, -1)[:, :n]


def _percentile_interval(samples: np.ndarray, alpha: float) -> tuple[float, float]:
    lo, hi = np.quantile(samples, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def paired_block_inference(
    policy_costs: Sequence[float],
    comparator_costs: Sequence[float],
    *,
    block_length: int,
    repetitions: int,
    seed: int,
    alpha: float,
) -> dict[str, float | list[float]]:
    policy = np.asarray(policy_costs, dtype=float)
    comparator = np.asarray(comparator_costs, dtype=float)
    if policy.shape != comparator.shape or policy.ndim != 1 or len(policy) < 2:
        raise StatisticalError("paired costs must be aligned one-dimensional arrays")
    if not np.all(np.isfinite(policy)) or not np.all(np.isfinite(comparator)):
        raise StatisticalError("paired costs must be finite")
    diff = policy - comparator
    indices = moving_block_indices(len(diff), block_length, repetitions, seed)
    boot = diff[indices]
    means = boot.mean(axis=1)
    medians = np.median(boot, axis=1)
    mean_ci = _percentile_interval(means, alpha)
    median_ci = _percentile_interval(medians, alpha)
    centered = diff - diff.mean()
    null_means = centered[indices].mean(axis=1)
    p_value = (1.0 + float(np.sum(np.abs(null_means) >= abs(diff.mean())))) / (
        repetitions + 1.0
    )
    comparator_mean = float(comparator.mean())
    relative = None if comparator_mean == 0.0 else 100.0 * float(diff.mean()) / abs(comparator_mean)
    sd = float(np.std(diff, ddof=1))
    standardized = 0.0 if sd == 0.0 else float(diff.mean()) / sd
    return {
        "episodes": int(len(diff)),
        "mean_difference_bps": float(diff.mean()),
        "median_difference_bps": float(np.median(diff)),
        "mean_ci95_bps": [mean_ci[0], mean_ci[1]],
        "median_ci95_bps": [median_ci[0], median_ci[1]],
        "raw_two_sided_p_value": float(p_value),
        "relative_change_percent": relative,
        "paired_standardized_effect": standardized,
        "policy_mean_cost_bps": float(policy.mean()),
        "comparator_mean_cost_bps": comparator_mean,
    }


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    if not p_values:
        return {}
    for value in p_values.values():
        if not 0.0 <= value <= 1.0:
            raise StatisticalError("p-values must be in [0,1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (name, value) in enumerate(ordered):
        candidate = min(1.0, (m - index) * value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def equal_instrument_paired_estimate(rows: Iterable[PairedHistoricalRow]) -> dict[str, object]:
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row.instrument, row.side, row.size_bucket, row.day)].append(
            row.policy_cost_bps - row.comparator_cost_bps
        )
    if not grouped:
        raise StatisticalError("historical aggregation requires rows")
    instrument_values: dict[str, list[float]] = defaultdict(list)
    for (instrument, _side, _size, _day), values in grouped.items():
        instrument_values[instrument].append(float(np.mean(values)))
    per_instrument = {
        instrument: float(np.mean(values))
        for instrument, values in sorted(instrument_values.items())
    }
    return {
        "equal_instrument_weighted_mean_difference_bps": float(
            np.mean(list(per_instrument.values()))
        ),
        "per_instrument_mean_difference_bps": per_instrument,
        "group_count": len(grouped),
        "instrument_count": len(per_instrument),
    }


def cvar95(values: Sequence[float]) -> float:
    x = np.asarray(values, dtype=float)
    if x.size == 0:
        raise StatisticalError("CVaR requires observations")
    cutoff = float(np.quantile(x, 0.95))
    tail = x[x >= cutoff]
    return float(tail.mean())



def bootstrap_tier1_guardrails(
    policy_costs: Sequence[float],
    comparator_costs: Sequence[float],
    policy_completion: Sequence[float],
    comparator_completion: Sequence[float],
    *,
    block_length: int,
    repetitions: int,
    seed: int,
    alpha: float = 0.05,
) -> dict[str, object]:
    policy = np.asarray(policy_costs, dtype=float)
    comparator = np.asarray(comparator_costs, dtype=float)
    policy_done = np.asarray(policy_completion, dtype=float)
    comparator_done = np.asarray(comparator_completion, dtype=float)
    if not (
        policy.shape == comparator.shape == policy_done.shape == comparator_done.shape
        and policy.ndim == 1
        and len(policy) >= 2
    ):
        raise StatisticalError("guardrail inputs must be aligned one-dimensional arrays")
    indices = moving_block_indices(len(policy), block_length, repetitions, seed)
    completion_diff = (policy_done[indices] - comparator_done[indices]).mean(axis=1)
    cvar_diff = np.empty(repetitions, dtype=float)
    for index, sample in enumerate(indices):
        cvar_diff[index] = cvar95(policy[sample]) - cvar95(comparator[sample])
    completion_ci = _percentile_interval(completion_diff, alpha)
    cvar_ci = _percentile_interval(cvar_diff, alpha)
    comparator_cvar = cvar95(comparator)
    cvar_margin = max(1.0, 0.05 * abs(comparator_cvar))
    return {
        "completion_difference": float(np.mean(policy_done - comparator_done)),
        "completion_ci95": [completion_ci[0], completion_ci[1]],
        "completion_pass": completion_ci[0] >= -0.01,
        "cvar95_difference_bps": cvar95(policy) - comparator_cvar,
        "cvar95_ci95_bps": [cvar_ci[0], cvar_ci[1]],
        "cvar95_allowed_margin_bps": cvar_margin,
        "cvar95_pass": cvar_ci[1] <= cvar_margin,
    }

def _ppo_aggregate(
    case_metrics: Mapping[str, Mapping[str, object]], seeds: Sequence[int]
) -> np.ndarray:
    arrays = [
        np.asarray(case_metrics[f"ppo_seed_{seed}"]["episode_costs_bps"], dtype=float)
        for seed in seeds
    ]
    lengths = {len(values) for values in arrays}
    if len(lengths) != 1:
        raise StatisticalError("PPO seed episode arrays are not aligned")
    return np.mean(np.stack(arrays, axis=0), axis=0)


def _policy_episode_costs(
    case_metrics: Mapping[str, Mapping[str, object]], policy: str, seeds: Sequence[int]
) -> np.ndarray:
    if policy == "ppo_aggregate":
        return _ppo_aggregate(case_metrics, seeds)
    if policy not in case_metrics:
        raise StatisticalError(f"unknown policy {policy}")
    return np.asarray(case_metrics[policy]["episode_costs_bps"], dtype=float)


def _nonoverlap_block_ci(
    diff: np.ndarray, block_length: int, repetitions: int, seed: int, alpha: float
) -> list[float]:
    blocks = [diff[i : i + block_length] for i in range(0, len(diff), block_length)]
    block_means = np.asarray([float(np.mean(block)) for block in blocks])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(block_means), size=(repetitions, len(block_means)))
    means = block_means[idx].mean(axis=1)
    lo, hi = _percentile_interval(means, alpha)
    return [lo, hi]


def _ranking_stability(
    case_metrics: Mapping[str, Mapping[str, object]],
    seeds: Sequence[int],
    policies: Sequence[str],
    *,
    block_length: int,
    repetitions: int,
    seed: int,
) -> dict[str, object]:
    arrays = np.stack([_policy_episode_costs(case_metrics, policy, seeds) for policy in policies])
    n = arrays.shape[1]
    indices = moving_block_indices(n, block_length, repetitions, seed)
    boot_means = np.stack([arr[indices].mean(axis=1) for arr in arrays], axis=1)
    winners = np.argmin(boot_means, axis=1)
    probs = {
        policy: float(np.mean(winners == index)) for index, policy in enumerate(policies)
    }
    point_means = arrays.mean(axis=1)
    point_index = int(np.argmin(point_means))
    point_winner = policies[point_index]
    return {
        "point_winner": point_winner,
        "point_mean_cost_bps": {
            policy: float(point_means[index]) for index, policy in enumerate(policies)
        },
        "bootstrap_win_probability": probs,
        "point_winner_bootstrap_probability": probs[point_winner],
        "winner_stable_at_0_80": probs[point_winner] >= 0.80,
    }


def _csv_bytes(rows: Sequence[Mapping[str, object]]) -> bytes:
    fields = [
        "case_id", "dimension", "setting", "policy", "comparator", "episodes",
        "mean_difference_bps", "median_difference_bps", "mean_ci95_low_bps",
        "mean_ci95_high_bps", "raw_two_sided_p_value", "holm_adjusted_p_value",
        "relative_change_percent", "paired_standardized_effect",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    return buffer.getvalue().encode("utf-8")


def generate_step29_artifacts(root: Path, config_path: Path | None = None) -> dict[str, object]:
    root = Path(root)
    config_path = config_path or root / "configs/statistics/step29_statistics_engineering.json"
    config = load_config(config_path)
    step28_path = root / "data/sample/robustness/step28-engineering-matrix/report.json"
    step28 = json.loads(step28_path.read_text(encoding="utf-8"))
    if step28.get("research_status") != config.research_status or step28.get("step") != 28:
        raise StatisticalError("Step 28 dependency identity mismatch")
    if step28["historical_cells"]["status"] != "blocked_gate_c":
        raise StatisticalError("Step 29 engineering run may not open historical results")
    # ppo_seed_policies are strings such as ppo_seed_27 in the report.
    seeds = tuple(int(str(x).split("_")[-1]) for x in step28["ppo_seed_policies"])
    central = step28["interactive_metrics"]["central_reference"]
    central_diff = _policy_episode_costs(central, "ppo_aggregate", seeds) - _policy_episode_costs(
        central, config.comparator, seeds
    )
    block_length, acf = select_block_length(
        central_diff,
        threshold=config.acf_threshold,
        minimum=config.min_block_length,
        maximum=config.max_block_length,
    )

    case_meta = {case["case_id"]: case for case in step28["interactive_cases"]}
    contrasts: list[dict[str, object]] = []
    holm_families: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    seed_counter = config.seed
    for case_id in sorted(step28["interactive_metrics"]):
        metrics = step28["interactive_metrics"][case_id]
        comparator = _policy_episode_costs(metrics, config.comparator, seeds)
        meta = case_meta[case_id]
        for policy in config.challenger_policies:
            policy_costs = _policy_episode_costs(metrics, policy, seeds)
            result = paired_block_inference(
                policy_costs,
                comparator,
                block_length=block_length,
                repetitions=config.bootstrap_repetitions,
                seed=seed_counter,
                alpha=config.alpha,
            )
            seed_counter += 1
            diff = policy_costs - comparator
            row: dict[str, object] = {
                "case_id": case_id,
                "dimension": meta["dimension"],
                "setting": meta["setting"],
                "policy": policy,
                "comparator": config.comparator,
                **result,
                "nonoverlap_block_mean_ci95_bps": _nonoverlap_block_ci(
                    diff,
                    block_length,
                    config.bootstrap_repetitions,
                    seed_counter,
                    config.alpha,
                ),
            }
            seed_counter += 1
            contrasts.append(row)
            family = (str(meta["dimension"]), policy)
            holm_families[family][case_id] = float(result["raw_two_sided_p_value"])

    holm_lookup: dict[tuple[str, str, str], float] = {}
    for (dimension, policy), values in holm_families.items():
        adjusted = holm_adjust(values)
        for case_id, value in adjusted.items():
            holm_lookup[(dimension, policy, case_id)] = value
    for row in contrasts:
        row["holm_adjusted_p_value"] = holm_lookup[
            (str(row["dimension"]), str(row["policy"]), str(row["case_id"]))
        ]

    ranking_policies = (config.comparator, *config.challenger_policies)
    ranking: dict[str, object] = {}
    for index, case_id in enumerate(sorted(step28["interactive_metrics"])):
        ranking[case_id] = _ranking_stability(
            step28["interactive_metrics"][case_id],
            seeds,
            ranking_policies,
            block_length=block_length,
            repetitions=config.ranking_bootstrap_repetitions,
            seed=config.seed + 10000 + index,
        )
    stable_count = sum(bool(value["winner_stable_at_0_80"]) for value in ranking.values())

    report: dict[str, object] = {
        "schema_version": "statistics-engineering-report-v1",
        "step": 29,
        "research_status": config.research_status,
        "gate_c_status": "blocked_no_admitted_historical_research_dataset",
        "gate_i_status": "engineering_statistics_complete_historical_confirmatory_pending",
        "locked_historical_test_opened": False,
        "tier1_confirmatory": {
            "contrast": "ML-MPC_minus_non-ML-MPC",
            "status": "blocked_gate_c",
            "test_data_accessed": False,
            "completion_guardrail_evaluated": False,
            "cvar95_guardrail_evaluated": False,
            "reason": "no admitted locked historical test and final ML-MPC selection unresolved",
        },
        "method": {
            "statistical_unit": "synthetic_episode_seed_as_pseudo_day_engineering_analogue",
            "historical_statistical_unit": "execution_episode_aggregated_within_whole_day",
            "bootstrap": "circular_moving_block_over_ordered_pseudo_days",
            "bootstrap_repetitions": config.bootstrap_repetitions,
            "ranking_bootstrap_repetitions": config.ranking_bootstrap_repetitions,
            "alpha": config.alpha,
            "selected_engineering_block_length": block_length,
            "block_length_selection_source": "central PPO aggregate minus liquidity-aware",
            "acf_by_lag": acf,
            "acf_threshold": config.acf_threshold,
            "historical_block_length_frozen": False,
            "iid_episode_bootstrap_used_for_primary_inference": False,
            "multiplicity": "Holm within challenger-by-stress-dimension engineering families",
            "tier3_boundary": (
                "all committed Step 28 robustness inference is exploratory engineering evidence"
            ),
        },
        "engineering_contrast_count": len(contrasts),
        "comparator": config.comparator,
        "challenger_policies": list(config.challenger_policies),
        "contrast_rows": contrasts,
        "ranking_stability": ranking,
        "ranking_summary": {
            "case_count": len(ranking),
            "stable_point_winner_cases_at_0_80": stable_count,
            "unstable_point_winner_cases_at_0_80": len(ranking) - stable_count,
        },
        "negative_results": {
            "holm_significant_cases_by_policy": {
                policy: sum(
                    float(row["holm_adjusted_p_value"]) < config.alpha
                    for row in contrasts
                    if row["policy"] == policy
                )
                for policy in config.challenger_policies
            },
            "confidence_intervals_crossing_zero": sum(
                float(row["mean_ci95_bps"][0]) <= 0.0 <= float(row["mean_ci95_bps"][1])
                for row in contrasts
            ),
            "unstable_point_winner_cases": len(ranking) - stable_count,
        },
        "historical_method_readiness": {
            "equal_instrument_weighted_aggregation_implemented": True,
            "moving_block_bootstrap_implemented": True,
            "holm_multiplicity_implemented": True,
            "completion_and_cvar_guardrails_implemented_but_not_evaluated": True,
            "historical_activation": "blocked_gate_c",
        },
        "scientific_boundary": [
            "synthetic pseudo-days are not historical trading days",
            "no Tier-1 p-value or guardrail result is reported",
            "no final strategy winner is selected from Step 29 engineering inference",
            "Holm-adjusted engineering stress results remain Tier-3 exploratory",
            "Step 30 owns formal performance claims",
        ],
    }

    output = root / "data/sample/statistics/step29-engineering-inference"
    output.mkdir(parents=True, exist_ok=True)
    report_bytes = (canonical_json(report) + "\n").encode("utf-8")
    contrasts_rows = []
    for row in contrasts:
        contrasts_rows.append(
            {
                **row,
                "mean_ci95_low_bps": row["mean_ci95_bps"][0],
                "mean_ci95_high_bps": row["mean_ci95_bps"][1],
            }
        )
    csv_bytes = _csv_bytes(contrasts_rows)
    ranking_bytes = (canonical_json(ranking) + "\n").encode("utf-8")
    (output / "report.json").write_bytes(report_bytes)
    (output / "contrasts.csv").write_bytes(csv_bytes)
    (output / "ranking-stability.json").write_bytes(ranking_bytes)
    manifest = {
        "schema_version": "statistics-engineering-manifest-v1",
        "step": 29,
        "research_status": config.research_status,
        "config_sha256": sha256_path(config_path),
        "step28_report_sha256": sha256_path(step28_path),
        "files": {
            "report.json": hashlib.sha256(report_bytes).hexdigest(),
            "contrasts.csv": hashlib.sha256(csv_bytes).hexdigest(),
            "ranking-stability.json": hashlib.sha256(ranking_bytes).hexdigest(),
        },
    }
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(manifest_bytes)
    return report
