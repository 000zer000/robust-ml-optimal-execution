#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import platform

from robust_execution.prediction.temporal_model_artifacts import FAMILY
from robust_execution.prediction.temporal_models import (
    benchmark_batch_one,
    build_sequences,
    generate_temporal_training_rows,
    load_model_from_payloads,
    load_temporal_model_config,
    split_sequences,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step23_temporal_deep_engineering.json"
MODEL_ROOT = ROOT / "data/sample/models/step23-temporal-deep-validation/models"
OUTPUT = ROOT / "results/validation/step23/inference_benchmark.json"


def main() -> None:
    config = load_temporal_model_config(CONFIG)
    sequences = build_sequences(generate_temporal_training_rows(config), config)
    holdout = split_sequences(sequences, config)["engineering_holdout"]
    models: dict[str, object] = {}
    for horizon in config.candidate_horizons:
        root = MODEL_ROOT / horizon / FAMILY
        card = json.loads((root / "model-card.json").read_text())
        weights = json.loads((root / "weights.json").read_text())
        model = load_model_from_payloads(card, weights, config)
        models[horizon] = benchmark_batch_one(model, holdout[0], config)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "step23-inference-benchmark-v1",
        "step": 23,
        "architecture": FAMILY,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "status": "engineering_machine_specific_not_step30_performance_claim",
        "models": models,
    }
    OUTPUT.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
