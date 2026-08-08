"""Step 26 behaviour cloning, covariate-shift diagnostics and corrective learning."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, log_loss
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

FEATURES = (
    "midpoint_ticks",
    "spread_ticks",
    "same_side_best_lots",
    "opposite_side_best_lots",
    "same_side_queue_share",
    "passive_fill_pressure",
    "passive_fill_probability",
    "elapsed_fraction",
    "filled_fraction",
    "remaining_fraction",
    "progress_lag",
    "time_remaining_fraction",
    "prediction_probability",
)
ACTION_FRACTIONS = {
    "passive_25": ("passive", 0.25),
    "passive_50": ("passive", 0.50),
    "passive_100": ("passive", 1.00),
    "aggressive_25": ("aggressive", 0.25),
    "aggressive_50": ("aggressive", 0.50),
    "aggressive_100": ("aggressive", 1.00),
    "no_action": ("none", 0.0),
}

DATASET_COLUMNS = (
    "episode_id",
    "step",
    "decision_id",
    "action_label",
    *FEATURES,
    "objective_bps",
)


class ImitationError(ValueError):
    """Raised when a Step 26 imitation-learning contract is violated."""


@dataclass(frozen=True)
class Step26Config:
    schema_version: str
    step: int
    research_status: str
    episode_counts: dict[str, int]
    steps_per_episode: int
    hidden_units: tuple[int, ...]
    alphas: tuple[float, ...]
    validation_dagger_agreement_floor: float
    validation_shift_trigger: float
    accepted_agreement_floor: float
    confidence_candidates: tuple[float, ...]
    training_z_quantile: float
    z_margin: float
    seed: int


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path) -> Step26Config:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = Step26Config(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        episode_counts={str(k): int(v) for k, v in raw["episode_counts"].items()},
        steps_per_episode=int(raw["steps_per_episode"]),
        hidden_units=tuple(int(v) for v in raw["hidden_units"]),
        alphas=tuple(float(v) for v in raw["alphas"]),
        validation_dagger_agreement_floor=float(raw["validation_dagger_agreement_floor"]),
        validation_shift_trigger=float(raw["validation_shift_trigger"]),
        accepted_agreement_floor=float(raw["accepted_agreement_floor"]),
        confidence_candidates=tuple(float(v) for v in raw["confidence_candidates"]),
        training_z_quantile=float(raw["training_z_quantile"]),
        z_margin=float(raw["z_margin"]),
        seed=int(raw["seed"]),
    )
    validate_config(config)
    return config


def validate_config(config: Step26Config) -> None:
    if config.schema_version != "imitation-engineering-config-v1" or config.step != 26:
        raise ImitationError("Step 26 config identity changed")
    if config.research_status != "synthetic_validation_only_non_research":
        raise ImitationError("Step 26 research boundary changed")
    required = {"train", "validation", "correction", "engineering_holdout", "ood"}
    if set(config.episode_counts) != required or min(config.episode_counts.values()) < 10:
        raise ImitationError("Step 26 episode split is incomplete")
    if config.steps_per_episode < 4:
        raise ImitationError("Step 26 needs at least four decisions per episode")
    if not config.hidden_units or min(config.hidden_units) < 2:
        raise ImitationError("invalid hidden-unit grid")
    if not config.alphas or min(config.alphas) <= 0:
        raise ImitationError("invalid regularisation grid")
    for value in (
        config.validation_dagger_agreement_floor,
        config.accepted_agreement_floor,
        config.training_z_quantile,
    ):
        if not 0 < value <= 1:
            raise ImitationError("invalid Step 26 probability-like threshold")
    if config.validation_shift_trigger <= 0 or config.z_margin < 0:
        raise ImitationError("invalid shift threshold")
    if tuple(sorted(set(config.confidence_candidates))) != config.confidence_candidates:
        raise ImitationError("confidence candidates must be sorted and unique")


def _episode_paths(segment: str, count: int, steps: int, ood: bool) -> list[dict[str, object]]:
    paths: list[dict[str, object]] = []
    segment_offset = sum(ord(ch) for ch in segment) % 17
    for episode in range(count):
        episode_id = f"{segment}-{episode:03d}"
        market: list[dict[str, int]] = []
        for step in range(steps):
            phase = (episode * 7 + step * 5 + segment_offset) % 13
            if ood:
                spread = 4 + 2 * ((phase + step) % 4)
                center = 100 + ((episode + step) % 7) - 3
                bid_qty = 8 + ((episode * 19 + step * 11) % 55)
                ask_qty = 8 + ((episode * 13 + step * 17) % 55)
            else:
                spread = 2 + 2 * ((phase + episode) % 2)
                center = 100 + ((episode + step) % 3) - 1
                bid_qty = 20 + ((episode * 17 + step * 23) % 240)
                ask_qty = 20 + ((episode * 29 + step * 13) % 240)
            bid = center - spread // 2
            ask = center + spread // 2
            market.append(
                {
                    "bid": bid,
                    "ask": ask,
                    "bid_quantity": bid_qty,
                    "ask_quantity": ask_qty,
                    "favorable": int((episode + step * 2 + phase) % 5 < (2 if ood else 3)),
                }
            )
        paths.append({"episode_id": episode_id, "market": market})
    return paths


def _oracle(executable: Path, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    fields = [
        "episode_id",
        "step",
        "now",
        "start",
        "deadline",
        "arrival",
        "bid",
        "ask",
        "bid_quantity",
        "ask_quantity",
        "favorable_passive_flow",
        "filled",
        "total",
        "decision_id",
        "prediction_probability",
    ]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        completed = subprocess.run(
            [str(executable), handle.name], check=True, text=True, capture_output=True
        )
    return [dict(row) for row in csv.DictReader(io.StringIO(completed.stdout))]


def _quantity(remaining: int, fraction: float) -> int:
    if fraction <= 0:
        return 0
    quantity = math.floor(remaining * fraction)
    return remaining if quantity == 0 else min(quantity, remaining)


def _apply_action(action: str, remaining: int, bid: int, ask: int) -> tuple[int, float]:
    if action not in ACTION_FRACTIONS:
        raise ImitationError(f"invalid imitation action {action}")
    mode, fraction = ACTION_FRACTIONS[action]
    quantity = _quantity(remaining, fraction)
    if mode == "passive":
        return quantity, float(bid)
    if mode == "aggressive":
        return quantity, float(ask)
    return 0, 0.0


def _prediction_probability(market: dict[str, int], filled: int, step: int, steps: int) -> float:
    depth_total = max(1, market["bid_quantity"] + market["ask_quantity"])
    depth_signal = (market["ask_quantity"] - market["bid_quantity"]) / depth_total
    flow_signal = -1.0 if market["favorable"] else 1.0
    urgency = step / max(1, steps - 1) - filled / 100.0
    value = 0.5 + 0.28 * depth_signal + 0.16 * flow_signal + 0.18 * urgency
    return float(min(0.95, max(0.05, value)))


def _state_row(
    episode_id: str,
    step: int,
    market: dict[str, int],
    filled: int,
    steps: int,
) -> dict[str, object]:
    start = 1_000_000
    interval = 1_000_000
    deadline = start + steps * interval
    return {
        "episode_id": episode_id,
        "step": step,
        "now": start + step * interval,
        "start": start,
        "deadline": deadline,
        "arrival": 100,
        "bid": market["bid"],
        "ask": market["ask"],
        "bid_quantity": market["bid_quantity"],
        "ask_quantity": market["ask_quantity"],
        "favorable_passive_flow": market["favorable"],
        "filled": filled,
        "total": 100,
        "decision_id": step + 1,
        "prediction_probability": _prediction_probability(market, filled, step, steps),
    }


def _features(row: dict[str, object]) -> np.ndarray:
    return np.asarray([float(row[name]) for name in FEATURES], dtype=np.float64)


def _write_teacher_table(path: Path, rows: list[dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DATASET_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in DATASET_COLUMNS})
    return sha256_path(path)


def _teacher_state_dataset(
    executable: Path, paths: list[dict[str, object]], steps: int
) -> list[dict[str, object]]:
    inputs: list[dict[str, object]] = []
    for episode_index, path in enumerate(paths):
        episode_id = str(path["episode_id"])
        for step in range(steps):
            market = path["market"][step]  # type: ignore[index]
            filled = (episode_index * 31 + step * 19 + (episode_index % 5) * 11) % 100
            inputs.append(_state_row(episode_id, step, market, filled, steps))
    return _oracle(executable, inputs)


def _teacher_rollout(
    executable: Path, paths: list[dict[str, object]], steps: int
) -> tuple[list[dict[str, object]], dict[str, dict[str, float]]]:
    filled = {str(path["episode_id"]): 0 for path in paths}
    notional = {str(path["episode_id"]): 0.0 for path in paths}
    rows: list[dict[str, object]] = []
    latencies: list[int] = []
    for step in range(steps):
        inputs: list[dict[str, object]] = []
        market_by_id: dict[str, dict[str, int]] = {}
        for path in paths:
            episode_id = str(path["episode_id"])
            if filled[episode_id] >= 100:
                continue
            market = path["market"][step]  # type: ignore[index]
            market_by_id[episode_id] = market
            inputs.append(_state_row(episode_id, step, market, filled[episode_id], steps))
        outputs = _oracle(executable, inputs)
        for output in outputs:
            episode_id = str(output["episode_id"])
            market = market_by_id[episode_id]
            quantity, price = _apply_action(
                str(output["action_label"]), 100 - filled[episode_id], market["bid"], market["ask"]
            )
            filled[episode_id] += quantity
            notional[episode_id] += quantity * price
            output["segment_episode_id"] = episode_id
            rows.append(output)
            latencies.append(int(output["teacher_latency_ns"]))
    metrics: dict[str, dict[str, float]] = {}
    for path in paths:
        episode_id = str(path["episode_id"])
        if filled[episode_id] < 100:
            residual = 100 - filled[episode_id]
            terminal_ask = int(path["market"][-1]["ask"]) + 1  # type: ignore[index]
            notional[episode_id] += residual * terminal_ask
            filled[episode_id] = 100
        average = notional[episode_id] / 100.0
        metrics[episode_id] = {
            "implementation_shortfall_bps": (average - 100.0) / 100.0 * 10_000.0,
            "complete": 1.0,
        }
    if rows:
        metrics["__latency__"] = {
            "p50_ns": float(np.percentile(latencies, 50)),
            "p95_ns": float(np.percentile(latencies, 95)),
        }
    return rows, metrics


@dataclass
class PolicyModel:
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    classes: tuple[str, ...]
    coefs: tuple[np.ndarray, np.ndarray]
    intercepts: tuple[np.ndarray, np.ndarray]
    hidden_units: int
    alpha: float

    def probabilities(self, matrix: np.ndarray) -> np.ndarray:
        z = (matrix - self.scaler_mean) / self.scaler_scale
        hidden = np.maximum(0.0, z @ self.coefs[0] + self.intercepts[0])
        logits = hidden @ self.coefs[1] + self.intercepts[1]
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return exp / exp.sum(axis=1, keepdims=True)

    def predict(self, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        probabilities = self.probabilities(matrix)
        indices = np.argmax(probabilities, axis=1)
        labels = np.asarray([self.classes[index] for index in indices], dtype=object)
        return labels, probabilities


def _matrix(rows: list[dict[str, object]]) -> np.ndarray:
    return np.vstack([_features(row) for row in rows])


def _labels(rows: list[dict[str, object]]) -> np.ndarray:
    return np.asarray([str(row["action_label"]) for row in rows], dtype=object)


def _fit_candidate(
    train_rows: list[dict[str, object]], hidden_units: int, alpha: float, seed: int
) -> PolicyModel:
    x = _matrix(train_rows)
    y = _labels(train_rows)
    scaler = StandardScaler().fit(x)
    model = MLPClassifier(
        hidden_layer_sizes=(hidden_units,),
        activation="relu",
        solver="lbfgs",
        alpha=alpha,
        max_iter=500,
        random_state=seed,
    ).fit(scaler.transform(x), y)
    return PolicyModel(
        scaler.mean_.astype(np.float64),
        scaler.scale_.astype(np.float64),
        tuple(str(value) for value in model.classes_),
        (model.coefs_[0].astype(np.float64), model.coefs_[1].astype(np.float64)),
        (model.intercepts_[0].astype(np.float64), model.intercepts_[1].astype(np.float64)),
        hidden_units,
        alpha,
    )


def _validation_score(model: PolicyModel, rows: list[dict[str, object]]) -> tuple[float, float]:
    labels = _labels(rows)
    predicted, probabilities = model.predict(_matrix(rows))
    accuracy = float(accuracy_score(labels, predicted))
    class_index = {label: index for index, label in enumerate(model.classes)}
    if any(label not in class_index for label in labels):
        return accuracy, float("inf")
    target = np.asarray([class_index[str(label)] for label in labels], dtype=np.int64)
    loss = float(log_loss(target, probabilities, labels=list(range(len(model.classes)))))
    return accuracy, loss


def _select_model(
    train_rows: list[dict[str, object]],
    validation_rows: list[dict[str, object]],
    config: Step26Config,
) -> tuple[PolicyModel, list[dict[str, float]]]:
    candidates: list[tuple[tuple[float, float, int, float], PolicyModel, dict[str, float]]] = []
    for hidden in config.hidden_units:
        for alpha in config.alphas:
            model = _fit_candidate(train_rows, hidden, alpha, config.seed)
            accuracy, loss = _validation_score(model, validation_rows)
            record = {
                "hidden_units": float(hidden),
                "alpha": float(alpha),
                "validation_action_agreement": accuracy,
                "validation_log_loss": loss,
            }
            key = (-accuracy, loss, hidden, alpha)
            candidates.append((key, model, record))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1], [item[2] for item in candidates]


def _shift(
    model: PolicyModel,
    teacher_rows: list[dict[str, object]],
    learner_rows: list[dict[str, object]],
) -> float:
    teacher_z = (_matrix(teacher_rows) - model.scaler_mean) / model.scaler_scale
    learner_z = (_matrix(learner_rows) - model.scaler_mean) / model.scaler_scale
    return float(np.max(np.abs(teacher_z.mean(axis=0) - learner_z.mean(axis=0))))


def _student_rollout(
    executable: Path,
    paths: list[dict[str, object]],
    steps: int,
    model: PolicyModel,
    confidence_threshold: float,
    z_threshold: float,
    use_fallback: bool,
) -> dict[str, object]:
    filled = {str(path["episode_id"]): 0 for path in paths}
    notional = {str(path["episode_id"]): 0.0 for path in paths}
    learner_rows: list[dict[str, object]] = []
    raw_correct = 0
    final_correct = 0
    decisions = 0
    fallback = 0
    for step in range(steps):
        inputs: list[dict[str, object]] = []
        market_by_id: dict[str, dict[str, int]] = {}
        for path in paths:
            episode_id = str(path["episode_id"])
            if filled[episode_id] >= 100:
                continue
            market = path["market"][step]  # type: ignore[index]
            market_by_id[episode_id] = market
            inputs.append(_state_row(episode_id, step, market, filled[episode_id], steps))
        outputs = _oracle(executable, inputs)
        for output in outputs:
            episode_id = str(output["episode_id"])
            vector = _features(output).reshape(1, -1)
            predicted, probabilities = model.predict(vector)
            raw_action = str(predicted[0])
            teacher_action = str(output["action_label"])
            z = np.abs((vector[0] - model.scaler_mean) / model.scaler_scale)
            uncertain = (
                float(probabilities.max()) < confidence_threshold or float(z.max()) > z_threshold
            )
            final_action = teacher_action if use_fallback and uncertain else raw_action
            fallback += int(use_fallback and uncertain)
            raw_correct += int(raw_action == teacher_action)
            final_correct += int(final_action == teacher_action)
            decisions += 1
            output["raw_student_action"] = raw_action
            output["final_action"] = final_action
            output["max_probability"] = float(probabilities.max())
            output["max_abs_training_z"] = float(z.max())
            learner_rows.append(output)
            market = market_by_id[episode_id]
            quantity, price = _apply_action(
                final_action, 100 - filled[episode_id], market["bid"], market["ask"]
            )
            filled[episode_id] += quantity
            notional[episode_id] += quantity * price
    shortfall: list[float] = []
    for path in paths:
        episode_id = str(path["episode_id"])
        if filled[episode_id] < 100:
            residual = 100 - filled[episode_id]
            terminal_ask = int(path["market"][-1]["ask"]) + 1  # type: ignore[index]
            notional[episode_id] += residual * terminal_ask
            filled[episode_id] = 100
        average = notional[episode_id] / 100.0
        shortfall.append((average - 100.0) / 100.0 * 10_000.0)
    return {
        "rows": learner_rows,
        "decisions": decisions,
        "raw_action_agreement": raw_correct / decisions if decisions else 1.0,
        "final_action_agreement": final_correct / decisions if decisions else 1.0,
        "fallback_rate": fallback / decisions if decisions else 0.0,
        "invalid_action_rate": 0.0,
        "completion_rate": 1.0,
        "mean_shortfall_bps": float(np.mean(shortfall)),
        "p95_shortfall_bps": float(np.percentile(shortfall, 95)),
    }


def _teacher_summary(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    values = [
        value["implementation_shortfall_bps"]
        for key, value in metrics.items()
        if not key.startswith("__")
    ]
    return {
        "mean_shortfall_bps": float(np.mean(values)),
        "p95_shortfall_bps": float(np.percentile(values, 95)),
        "completion_rate": 1.0,
    }


def _choose_fallback_threshold(
    model: PolicyModel,
    validation_rows: list[dict[str, object]],
    config: Step26Config,
    z_threshold: float,
) -> float:
    x = _matrix(validation_rows)
    labels = _labels(validation_rows)
    predicted, probabilities = model.predict(x)
    z = np.max(np.abs((x - model.scaler_mean) / model.scaler_scale), axis=1)
    best = config.confidence_candidates[-1]
    best_coverage = -1.0
    for threshold in config.confidence_candidates:
        accepted = (probabilities.max(axis=1) >= threshold) & (z <= z_threshold)
        count = int(accepted.sum())
        if count == 0:
            continue
        agreement = float(np.mean(predicted[accepted] == labels[accepted]))
        coverage = count / len(labels)
        if agreement >= config.accepted_agreement_floor and coverage > best_coverage:
            best = threshold
            best_coverage = coverage
    return best


def _export_model(model: PolicyModel) -> dict[str, object]:
    return {
        "schema_version": "imitation-policy-artifact-v1",
        "feature_names": list(FEATURES),
        "classes": list(model.classes),
        "hidden_units": model.hidden_units,
        "alpha": model.alpha,
        "scaler_mean": model.scaler_mean.tolist(),
        "scaler_scale": model.scaler_scale.tolist(),
        "coefs": [matrix.tolist() for matrix in model.coefs],
        "intercepts": [vector.tolist() for vector in model.intercepts],
    }


def _reconstruct_model(payload: dict[str, object]) -> PolicyModel:
    return PolicyModel(
        np.asarray(payload["scaler_mean"], dtype=np.float64),
        np.asarray(payload["scaler_scale"], dtype=np.float64),
        tuple(str(v) for v in payload["classes"]),
        (
            np.asarray(payload["coefs"][0], dtype=np.float64),  # type: ignore[index]
            np.asarray(payload["coefs"][1], dtype=np.float64),  # type: ignore[index]
        ),
        (
            np.asarray(payload["intercepts"][0], dtype=np.float64),  # type: ignore[index]
            np.asarray(payload["intercepts"][1], dtype=np.float64),  # type: ignore[index]
        ),
        int(payload["hidden_units"]),
        float(payload["alpha"]),
    )


def _class_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for label in _labels(rows):
        result[str(label)] = result.get(str(label), 0) + 1
    return dict(sorted(result.items()))


def generate_step26_artifacts(
    root: Path,
    executable: Path,
    config_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        name: _episode_paths(name, count, config.steps_per_episode, name == "ood")
        for name, count in config.episode_counts.items()
    }
    teacher: dict[str, tuple[list[dict[str, object]], dict[str, dict[str, float]]]] = {}
    for name in ("engineering_holdout", "ood"):
        teacher[name] = _teacher_rollout(executable, paths[name], config.steps_per_episode)
    train_rows = _teacher_state_dataset(executable, paths["train"], config.steps_per_episode)
    validation_rows = _teacher_state_dataset(
        executable, paths["validation"], config.steps_per_episode
    )
    model, candidate_records = _select_model(train_rows, validation_rows, config)

    train_z = np.max(np.abs((_matrix(train_rows) - model.scaler_mean) / model.scaler_scale), axis=1)
    z_threshold = float(np.quantile(train_z, config.training_z_quantile) + config.z_margin)
    confidence = _choose_fallback_threshold(model, validation_rows, config, z_threshold)
    validation_raw = _student_rollout(
        executable, paths["validation"], config.steps_per_episode, model, 0.0, z_threshold, False
    )
    validation_shift = _shift(
        model,
        validation_rows,
        validation_raw["rows"],  # type: ignore[arg-type]
    )
    trigger = (
        float(validation_raw["raw_action_agreement"]) < config.validation_dagger_agreement_floor
        or validation_shift > config.validation_shift_trigger
        or float(validation_raw["completion_rate"]) < 1.0
    )
    dagger_rows: list[dict[str, object]] = []
    initial_model = model
    if trigger:
        correction = _student_rollout(
            executable,
            paths["correction"],
            config.steps_per_episode,
            model,
            0.0,
            z_threshold,
            False,
        )
        dagger_rows = list(correction["rows"])  # type: ignore[arg-type]
        model = _fit_candidate(
            train_rows + dagger_rows, initial_model.hidden_units, initial_model.alpha, config.seed
        )
        combined_x = _matrix(train_rows + dagger_rows)
        train_z = np.max(np.abs((combined_x - model.scaler_mean) / model.scaler_scale), axis=1)
        z_threshold = float(np.quantile(train_z, config.training_z_quantile) + config.z_margin)
        confidence = _choose_fallback_threshold(model, validation_rows, config, z_threshold)

    table_rows = {
        "train": train_rows,
        "validation": validation_rows,
        "correction": dagger_rows,
        "engineering_holdout": teacher["engineering_holdout"][0],
        "ood": teacher["ood"][0],
    }
    table_manifest: dict[str, object] = {}
    for split_name, rows in table_rows.items():
        table_path = output_dir / f"teacher_{split_name}.csv"
        table_manifest[split_name] = {
            "path": table_path.name,
            "rows": len(rows),
            "sha256": _write_teacher_table(table_path, rows),
        }
    split_manifest = {
        "schema_version": "imitation-teacher-dataset-manifest-v1",
        "step": 26,
        "research_status": config.research_status,
        "config_sha256": sha256_path(config_path),
        "teacher_policy": "step24_shared_ml_mpc_engineering_teacher",
        "teacher_base_mpc_configuration": "step20-non-ml-mpc-v1",
        "teacher_prediction_input": "causal_synthetic_engineering_risk_non_research",
        "episode_ids": {
            name: [str(path["episode_id"]) for path in paths[name]] for name in sorted(paths)
        },
        "tables": table_manifest,
        "dagger_triggered": trigger,
        "dagger_rounds": 1 if trigger else 0,
    }
    split_manifest_path = output_dir / "teacher-dataset-manifest.json"
    split_manifest_path.write_text(canonical_json(split_manifest) + "\n", encoding="utf-8")

    final_validation = _student_rollout(
        executable, paths["validation"], config.steps_per_episode, model, 0.0, z_threshold, False
    )
    final_shift = _shift(model, validation_rows, final_validation["rows"])  # type: ignore[arg-type]
    evaluations: dict[str, object] = {}
    for name in ("engineering_holdout", "ood"):
        raw = _student_rollout(
            executable, paths[name], config.steps_per_episode, model, confidence, z_threshold, False
        )
        fallback = _student_rollout(
            executable, paths[name], config.steps_per_episode, model, confidence, z_threshold, True
        )
        teacher_summary = _teacher_summary(teacher[name][1])
        raw_summary = {key: value for key, value in raw.items() if key != "rows"}
        fallback_summary = {key: value for key, value in fallback.items() if key != "rows"}
        raw_summary["mean_shortfall_delta_vs_teacher_bps"] = (
            float(raw_summary["mean_shortfall_bps"]) - teacher_summary["mean_shortfall_bps"]
        )
        raw_summary["p95_shortfall_delta_vs_teacher_bps"] = (
            float(raw_summary["p95_shortfall_bps"]) - teacher_summary["p95_shortfall_bps"]
        )
        fallback_summary["mean_shortfall_delta_vs_teacher_bps"] = (
            float(fallback_summary["mean_shortfall_bps"]) - teacher_summary["mean_shortfall_bps"]
        )
        fallback_summary["p95_shortfall_delta_vs_teacher_bps"] = (
            float(fallback_summary["p95_shortfall_bps"]) - teacher_summary["p95_shortfall_bps"]
        )
        evaluations[name] = {
            "teacher": teacher_summary,
            "student_raw": raw_summary,
            "student_with_teacher_fallback": fallback_summary,
            "state_shift_max_abs_standardized_mean": _shift(
                model,
                teacher[name][0],
                raw["rows"],  # type: ignore[arg-type]
            ),
        }

    artifact = _export_model(model)
    model_path = output_dir / "policy.json"
    model_path.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
    reconstructed = _reconstruct_model(json.loads(model_path.read_text(encoding="utf-8")))
    probe = _matrix(validation_rows[: min(25, len(validation_rows))])
    if not np.array_equal(model.probabilities(probe), reconstructed.probabilities(probe)):
        raise ImitationError("serialized Step 26 model is not semantically exact")

    report: dict[str, object] = {
        "schema_version": "imitation-engineering-report-v1",
        "step": 26,
        "research_status": config.research_status,
        "teacher": {
            "policy": "step24_shared_ml_mpc_engineering_teacher",
            "solver": "cpp_exact_shared_mpc",
            "base_mpc_configuration": "step20-non-ml-mpc-v1",
            "prediction_input": "causal_synthetic_engineering_risk_non_research",
            "prediction_risk_weight_bps": 10000.0,
            "training_class_counts": _class_counts(train_rows),
        },
        "data": {
            "episode_counts": config.episode_counts,
            "steps_per_episode": config.steps_per_episode,
            "teacher_rows": {
                "train": len(train_rows),
                "validation": len(validation_rows),
                "engineering_holdout": len(teacher["engineering_holdout"][0]),
                "ood": len(teacher["ood"][0]),
            },
            "correction_rows_added": len(dagger_rows),
        },
        "model_selection": {
            "validation_only_candidates": candidate_records,
            "selected_hidden_units": initial_model.hidden_units,
            "selected_alpha": initial_model.alpha,
            "hyperparameters_frozen_before_correction": True,
        },
        "covariate_shift": {
            "initial_validation_raw_action_agreement": float(
                validation_raw["raw_action_agreement"]
            ),
            "initial_validation_shift": validation_shift,
            "dagger_triggered": trigger,
            "dagger_rounds": 1 if trigger else 0,
            "final_validation_raw_action_agreement": float(
                final_validation["raw_action_agreement"]
            ),
            "final_validation_shift": final_shift,
        },
        "fallback": {
            "kind": "teacher_mpc_fallback_engineering_only",
            "confidence_threshold": confidence,
            "max_abs_training_z_threshold": z_threshold,
            "threshold_selected_on_validation_only": True,
        },
        "evaluation": evaluations,
        "artifact": {
            "path": "policy.json",
            "sha256": sha256_path(model_path),
            "format": "canonical_json_named_tensors",
            "teacher_dataset_manifest_path": "teacher-dataset-manifest.json",
            "teacher_dataset_manifest_sha256": sha256_path(split_manifest_path),
        },
        "research_selections": {
            "historical_test_opened": False,
            "research_policy_selected": False,
            "rl_started": False,
        },
    }
    payload = canonical_json(report)
    report["payload_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    report_path = output_dir / "report.json"
    report_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
    return report


def validate_step26_report(report: dict[str, object]) -> None:
    if (
        report.get("schema_version") != "imitation-engineering-report-v1"
        or report.get("step") != 26
    ):
        raise ImitationError("Step 26 report identity changed")
    if report.get("research_status") != "synthetic_validation_only_non_research":
        raise ImitationError("Step 26 report research boundary changed")
    selections = report["research_selections"]
    if any(bool(value) for value in selections.values()):  # type: ignore[union-attr]
        raise ImitationError("Step 26 engineering report crossed a research boundary")
    evaluation = report["evaluation"]
    for name in ("engineering_holdout", "ood"):
        block = evaluation[name]  # type: ignore[index]
        for policy_name in ("student_raw", "student_with_teacher_fallback"):
            policy_block = block[policy_name]
            if float(policy_block["completion_rate"]) != 1.0:
                raise ImitationError(f"{name}: imitation policy failed hard completion")
            if float(policy_block["invalid_action_rate"]) != 0.0:
                raise ImitationError(f"{name}: invalid imitation action observed")
