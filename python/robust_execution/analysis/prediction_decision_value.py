"""Step 25 prediction-quality versus decision-value engineering analysis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable

import numpy as np
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

from robust_execution.historical_replay.tables import read_table


HORIZONS = ("250ms", "1s", "5s")
ABLATIONS = (
    "calibrated_model",
    "training_base_rate",
    "shuffled_within_day_instrument",
    "stale",
    "uncalibrated_model",
    "perfect_event_oracle",
)
CONTROLLER_KEYS = {
    "calibrated_model": "calibrated",
    "training_base_rate": "training_base_rate_ablation",
    "shuffled_within_day_instrument": "shuffled_within_day_instrument_ablation",
    "stale": "stale_ablation",
    "uncalibrated_model": "uncalibrated_ablation",
    "perfect_event_oracle": "perfect_event_oracle_ablation",
}


class PredictionDecisionValueError(ValueError):
    """Raised when Step 25 analysis contracts are violated."""


@dataclass(frozen=True)
class Step25Config:
    schema_version: str
    step: int
    research_status: str
    source_dataset: str
    prediction_family: str
    candidate_horizons: tuple[str, ...]
    ece_bins: int
    weight_grid_bps: tuple[float, ...]
    primary_horizon_selected: bool
    final_model_family_selected: bool
    use_engineering_results_for_research_selection: bool


def load_config(path: Path) -> Step25Config:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = Step25Config(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        source_dataset=str(raw["source_dataset"]),
        prediction_family=str(raw["prediction_family"]),
        candidate_horizons=tuple(str(value) for value in raw["candidate_horizons"]),
        ece_bins=int(raw["ece_bins"]),
        weight_grid_bps=tuple(float(value) for value in raw["weight_grid_bps"]),
        primary_horizon_selected=bool(raw["primary_horizon_selected"]),
        final_model_family_selected=bool(raw["final_model_family_selected"]),
        use_engineering_results_for_research_selection=bool(
            raw["use_engineering_results_for_research_selection"]
        ),
    )
    validate_config(config)
    return config


def validate_config(config: Step25Config) -> None:
    if config.schema_version != "prediction-decision-value-engineering-config-v1":
        raise PredictionDecisionValueError("Step 25 config schema changed")
    if config.step != 25:
        raise PredictionDecisionValueError("Step 25 config identity changed")
    if config.research_status != "synthetic_validation_only_non_research":
        raise PredictionDecisionValueError("Step 25 engineering boundary changed")
    if config.candidate_horizons != HORIZONS:
        raise PredictionDecisionValueError("Step 25 candidate horizons changed")
    if config.ece_bins < 2:
        raise PredictionDecisionValueError("ECE requires at least two bins")
    if not config.weight_grid_bps or config.weight_grid_bps[0] != 0.0:
        raise PredictionDecisionValueError("weight grid must start at zero")
    if any(not math.isfinite(value) or value < 0.0 for value in config.weight_grid_bps):
        raise PredictionDecisionValueError("weight grid must be finite and non-negative")
    if tuple(sorted(set(config.weight_grid_bps))) != config.weight_grid_bps:
        raise PredictionDecisionValueError("weight grid must be strictly increasing and unique")
    if config.primary_horizon_selected or config.final_model_family_selected:
        raise PredictionDecisionValueError(
            "Step 25 engineering fixture may not select research model"
        )
    if config.use_engineering_results_for_research_selection:
        raise PredictionDecisionValueError("engineering results cannot drive research selection")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _clip(probabilities: np.ndarray) -> np.ndarray:
    return np.clip(probabilities.astype(np.float64), 1e-9, 1.0 - 1e-9)


def _ece(target: np.ndarray, probability: np.ndarray, bins: int) -> float:
    result = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        mask = (probability >= low) & (
            probability < high if index + 1 < bins else probability <= high
        )
        count = int(mask.sum())
        if count:
            result += count / len(target) * abs(
                float(probability[mask].mean()) - float(target[mask].mean())
            )
    return result


def probability_metrics(
    target: Iterable[int], probability: Iterable[float], ece_bins: int
) -> dict[str, object]:
    y = np.asarray(tuple(target), dtype=np.int64)
    p = _clip(np.asarray(tuple(probability), dtype=np.float64))
    if len(y) == 0 or len(y) != len(p):
        raise PredictionDecisionValueError("metric vectors must be non-empty and aligned")
    classes = set(int(value) for value in y)
    return {
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "prevalence": float(y.mean()),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(np.mean((p - y) ** 2)),
        "ece": float(_ece(y, p, ece_bins)),
        "roc_auc": float(roc_auc_score(y, p)) if classes == {0, 1} else None,
        "pr_auc": float(average_precision_score(y, p)) if classes == {0, 1} else None,
    }


def _grouped_indices(rows: list[dict[str, object]]) -> list[list[int]]:
    groups: dict[tuple[int, str, str], list[int]] = {}
    for index, row in enumerate(rows):
        key = (int(row["day_index"]), str(row["symbol"]), str(row["passive_side"]))
        groups.setdefault(key, []).append(index)
    ordered: list[list[int]] = []
    for key in sorted(groups):
        indices = groups[key]
        indices.sort(key=lambda index: int(rows[index]["end_decision_index"]))
        ordered.append(indices)
    return ordered


def ablation_probabilities(
    rows: list[dict[str, object]], base_rate: float
) -> dict[str, np.ndarray]:
    calibrated = np.asarray(
        [float(row["calibrated_probability"]) for row in rows], dtype=np.float64
    )
    uncalibrated = np.asarray(
        [float(row["uncalibrated_probability"]) for row in rows], dtype=np.float64
    )
    target = np.asarray([int(row["target"]) for row in rows], dtype=np.float64)
    base = np.full(len(rows), base_rate, dtype=np.float64)
    shuffled = calibrated.copy()
    stale = base.copy()
    for indices in _grouped_indices(rows):
        if len(indices) > 1:
            rotated = indices[1:] + indices[:1]
            for destination, source in zip(indices, rotated, strict=True):
                shuffled[destination] = calibrated[source]
            for position in range(1, len(indices)):
                stale[indices[position]] = calibrated[indices[position - 1]]
    return {
        "calibrated_model": calibrated,
        "training_base_rate": base,
        "shuffled_within_day_instrument": shuffled,
        "stale": stale,
        "uncalibrated_model": uncalibrated,
        "perfect_event_oracle": target,
    }


def load_prediction_analysis(
    root: Path, config: Step25Config
) -> tuple[dict[str, object], dict[str, object]]:
    models_root = root / "data/sample/models/step23-temporal-deep-validation/models"
    step23_report_path = root / "data/sample/models/step23-temporal-deep-validation/report.json"
    step23_report = json.loads(step23_report_path.read_text(encoding="utf-8"))
    output: dict[str, object] = {}
    sources: dict[str, object] = {
        "step23_report_sha256": sha256_path(step23_report_path),
        "horizons": {},
    }
    for horizon in config.candidate_horizons:
        model_root = models_root / horizon / config.prediction_family
        rows = read_table(model_root, "tables/engineering_holdout_predictions/columns.json.gz")
        card_path = model_root / "model-card.json"
        card = json.loads(card_path.read_text(encoding="utf-8"))
        base_rate = float(card["training_prevalence"])
        probabilities = ablation_probabilities(rows, base_rate)
        targets = [int(row["target"]) for row in rows]
        metrics = {
            name: probability_metrics(targets, values, config.ece_bins)
            for name, values in probabilities.items()
        }
        ranking = sorted(
            ABLATIONS,
            key=lambda name: (
                float(metrics[name]["log_loss"]),
                float(metrics[name]["brier"]),
                name,
            ),
        )
        output[horizon] = {
            "rows": len(rows),
            "training_base_rate": base_rate,
            "metrics": metrics,
            "log_loss_ranking_best_to_worst": ranking,
        }
        prediction_data = (
            model_root / "tables/engineering_holdout_predictions/columns.json.gz"
        )
        expected_data_hash = step23_report["models"][horizon]["prediction_data_sha256"]
        if sha256_path(prediction_data) != expected_data_hash:
            raise PredictionDecisionValueError(
                f"{horizon}: Step 23 prediction table does not match report hash"
            )
        sources["horizons"][horizon] = {
            "model_card_sha256": sha256_path(card_path),
            "prediction_data_sha256": expected_data_hash,
        }
    return output, sources


def _controller_report(executable: Path, weight: float) -> dict[str, object]:
    env = os.environ.copy()
    env["RE_ML_MPC_WEIGHT_BPS"] = f"{weight:.1f}"
    completed = subprocess.run(
        [str(executable)],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return json.loads(completed.stdout)


def action_distance(left: list[str], right: list[str]) -> int:
    shared = min(len(left), len(right))
    return sum(left[index] != right[index] for index in range(shared)) + abs(
        len(left) - len(right)
    )


def load_decision_sweep(
    executable: Path, config: Step25Config
) -> dict[str, object]:
    reports = [_controller_report(executable, weight) for weight in config.weight_grid_bps]
    if any(report["payload"]["locked_research_test_opened"] for report in reports):
        raise PredictionDecisionValueError("controller sweep opened locked research test")
    baseline = reports[0]["payload"]["non_ml_mpc"]
    baseline_actions = list(baseline["actions"])
    baseline_shortfall = int(baseline["implementation_shortfall_bps"])
    horizons: dict[str, object] = {}
    for horizon in config.candidate_horizons:
        records: dict[str, object] = {}
        for ablation in ABLATIONS:
            controller_key = CONTROLLER_KEYS[ablation]
            sweep: list[dict[str, object]] = []
            first_change: float | None = None
            for weight, report in zip(config.weight_grid_bps, reports, strict=True):
                episode = report["payload"]["horizons"][horizon][controller_key]
                actions = list(episode["actions"])
                distance = action_distance(actions, baseline_actions)
                if distance and first_change is None:
                    first_change = weight
                sweep.append(
                    {
                        "weight_bps": weight,
                        "actions": actions,
                        "action_distance_from_non_ml": distance,
                        "implementation_shortfall_bps": int(
                            episode["implementation_shortfall_bps"]
                        ),
                        "shortfall_delta_bps_vs_non_ml": int(
                            episode["implementation_shortfall_bps"]
                        )
                        - baseline_shortfall,
                        "complete": bool(episode["complete"]),
                    }
                )
            records[ablation] = {
                "first_grid_weight_with_action_change_bps": first_change,
                "sweep": sweep,
            }
        zero_weight_episode = reports[0]["payload"]["horizons"][horizon][
            "prediction_weight_zero_ablation"
        ]
        if list(zero_weight_episode["actions"]) != baseline_actions:
            raise PredictionDecisionValueError("zero-weight control changed baseline actions")
        horizons[horizon] = records
    return {
        "baseline_non_ml": {
            "actions": baseline_actions,
            "implementation_shortfall_bps": baseline_shortfall,
        },
        "weight_grid_bps": list(config.weight_grid_bps),
        "horizons": horizons,
    }


def relation_label(
    reference_metrics: dict[str, object],
    candidate_metrics: dict[str, object],
    reference_decision: dict[str, object],
    candidate_decision: dict[str, object],
) -> str:
    prediction_better = float(candidate_metrics["log_loss"]) < float(
        reference_metrics["log_loss"]
    ) - 1e-12
    decision_changed = candidate_decision["actions"] != reference_decision["actions"]
    if prediction_better and not decision_changed:
        return "prediction_improved_decision_unchanged"
    if prediction_better and decision_changed:
        return "prediction_improved_decision_changed"
    if not prediction_better and decision_changed:
        return "prediction_not_improved_decision_changed"
    return "prediction_not_improved_decision_unchanged"


def build_relationships(
    prediction: dict[str, object], decision: dict[str, object]
) -> dict[str, object]:
    output: dict[str, object] = {}
    comparisons = (
        ("training_base_rate", "calibrated_model"),
        ("shuffled_within_day_instrument", "calibrated_model"),
        ("stale", "calibrated_model"),
        ("uncalibrated_model", "calibrated_model"),
        ("calibrated_model", "perfect_event_oracle"),
    )
    for horizon in HORIZONS:
        horizon_output: list[dict[str, object]] = []
        metrics = prediction[horizon]["metrics"]
        sweeps = decision["horizons"][horizon]
        for reference, candidate in comparisons:
            by_weight = []
            for ref_row, cand_row in zip(
                sweeps[reference]["sweep"], sweeps[candidate]["sweep"], strict=True
            ):
                by_weight.append(
                    {
                        "weight_bps": cand_row["weight_bps"],
                        "relationship": relation_label(
                            metrics[reference], metrics[candidate], ref_row, cand_row
                        ),
                        "decision_shortfall_delta_candidate_minus_reference_bps": int(
                            cand_row["implementation_shortfall_bps"]
                        )
                        - int(ref_row["implementation_shortfall_bps"]),
                    }
                )
            horizon_output.append(
                {
                    "reference": reference,
                    "candidate": candidate,
                    "candidate_log_loss_delta": float(metrics[candidate]["log_loss"])
                    - float(metrics[reference]["log_loss"]),
                    "by_weight": by_weight,
                }
            )
        output[horizon] = horizon_output
    return output



def build_engineering_summary(
    prediction: dict[str, object],
    decision: dict[str, object],
    relationships: dict[str, object],
) -> dict[str, object]:
    relationship_counts = {
        "prediction_improved_decision_unchanged": 0,
        "prediction_improved_decision_changed": 0,
        "prediction_not_improved_decision_unchanged": 0,
        "prediction_not_improved_decision_changed": 0,
    }
    for comparisons in relationships.values():
        for comparison in comparisons:
            for row in comparison["by_weight"]:
                relationship_counts[row["relationship"]] += 1

    horizon_summary: dict[str, object] = {}
    any_changed_improved = False
    oracle_worsened = False
    for horizon in HORIZONS:
        metrics = prediction[horizon]["metrics"]
        sweeps = decision["horizons"][horizon]
        changed_deltas: list[int] = []
        for ablation in ABLATIONS:
            for row in sweeps[ablation]["sweep"]:
                if row["action_distance_from_non_ml"]:
                    delta = int(row["shortfall_delta_bps_vs_non_ml"])
                    changed_deltas.append(delta)
                    any_changed_improved = any_changed_improved or delta < 0
                    if ablation == "perfect_event_oracle" and delta > 0:
                        oracle_worsened = True
        horizon_summary[horizon] = {
            "calibrated_minus_uncalibrated_log_loss": float(
                metrics["calibrated_model"]["log_loss"]
            )
            - float(metrics["uncalibrated_model"]["log_loss"]),
            "calibrated_first_grid_weight_with_action_change_bps": sweeps[
                "calibrated_model"
            ]["first_grid_weight_with_action_change_bps"],
            "uncalibrated_first_grid_weight_with_action_change_bps": sweeps[
                "uncalibrated_model"
            ]["first_grid_weight_with_action_change_bps"],
            "oracle_first_grid_weight_with_action_change_bps": sweeps[
                "perfect_event_oracle"
            ]["first_grid_weight_with_action_change_bps"],
            "changed_action_shortfall_delta_min_bps": min(changed_deltas)
            if changed_deltas
            else None,
            "changed_action_shortfall_delta_max_bps": max(changed_deltas)
            if changed_deltas
            else None,
        }
    return {
        "relationship_counts": relationship_counts,
        "prediction_metric_improvement_without_decision_change_observed": (
            relationship_counts["prediction_improved_decision_unchanged"] > 0
        ),
        "prediction_metric_degradation_with_decision_change_observed": (
            relationship_counts["prediction_not_improved_decision_changed"] > 0
        ),
        "perfect_label_oracle_can_worsen_execution_fixture": oracle_worsened,
        "any_changed_action_improved_implementation_shortfall_fixture": any_changed_improved,
        "lower_implementation_shortfall_is_better": True,
        "horizons": horizon_summary,
    }

def build_report(root: Path, config: Step25Config, executable: Path) -> dict[str, object]:
    prediction, sources = load_prediction_analysis(root, config)
    decision = load_decision_sweep(executable, config)
    relationships = build_relationships(prediction, decision)
    summary = build_engineering_summary(prediction, decision, relationships)
    payload = {
        "schema_version": "prediction-decision-value-report-v1",
        "step": 25,
        "research_status": config.research_status,
        "gate_c_historical_activation": False,
        "primary_horizon_selected": False,
        "final_model_family_selected": False,
        "locked_research_test_opened": False,
        "engineering_results_used_for_research_selection": False,
        "prediction_family": config.prediction_family,
        "candidate_horizons": list(config.candidate_horizons),
        "prediction_analysis": prediction,
        "decision_sensitivity": decision,
        "prediction_decision_relationships": relationships,
        "engineering_summary": summary,
        "source_artifacts": sources,
    }
    canonical = canonical_json(payload)
    return {"payload": payload, "sha256": sha256_bytes(canonical.encode("utf-8"))}
