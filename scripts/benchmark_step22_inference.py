#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import sklearn
from threadpoolctl import threadpool_limits

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.historical_replay.tables import read_table
from robust_execution.prediction.simple_model_artifacts import FAMILIES
from robust_execution.prediction.simple_models import (
    TrainingRow,
    benchmark_batch_one,
    load_serialized_model,
    load_simple_model_config,
    split_for_day,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step22_simple_models_engineering.json"
DATASET = ROOT / "data/sample/models/step22-simple-models-validation"
OUTPUT = ROOT / "results/validation/step22/inference_benchmark.json"


def main() -> None:
    config = load_simple_model_config(CONFIG)
    raw_rows = read_table(DATASET, "tables/engineering_training_rows/columns.json.gz")
    rows = [
        TrainingRow(
            row_id=str(raw["row_id"]),
            symbol=str(raw["symbol"]),
            passive_side=str(raw["passive_side"]),  # type: ignore[arg-type]
            day_index=int(raw["day_index"]),
            decision_index=int(raw["decision_index"]),
            feature={name: int(raw[name]) for name in config.feature_names},
            labels={
                name: int(raw[name])
                for name in (
                    "quote_depletion_250ms",
                    "quote_depletion_1s",
                    "quote_depletion_5s",
                )
            },
        )
        for raw in raw_rows
        if split_for_day(int(raw["day_index"]), config.split_days) == "engineering_holdout"
    ]
    results: dict[str, object] = {}
    with threadpool_limits(limits=1):
        for horizon in config.candidate_horizons:
            results[horizon] = {}
            for family in FAMILIES:
                model = load_serialized_model(DATASET / "models" / horizon / family / "model.pkl")
                results[horizon][family] = benchmark_batch_one(model, rows, config, repetitions=500)
    payload = {
        "schema_version": "step22-inference-benchmark-v1",
        "step": 22,
        "research_status": "synthetic_validation_only_non_research",
        "performance_claim_status": "engineering_machine_specific_not_step30_performance_claim",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "numpy": np.__version__,
        "sklearn": sklearn.__version__,
        "thread_limit": 1,
        "results": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(canonical_json_bytes(payload) + b"\n")
    print(json.dumps({"status": "ok", "path": str(OUTPUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
