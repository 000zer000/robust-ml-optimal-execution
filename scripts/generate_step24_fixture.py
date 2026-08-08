#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/sample/controller/step24-ml-mpc-validation"
MODELS = ROOT / "data/sample/models/step23-temporal-deep-validation/models"
REPORT_EXE = native_executable(ROOT, "robust_execution_ml_mpc_demo")
HORIZONS = ("250ms", "1s", "5s")
ENDPOINT_TIMES = (1000, 1250, 1500, 1750)


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_prediction_columns(horizon: str) -> dict[str, list[object]]:
    path = (
        MODELS
        / horizon
        / "causal_conv1d_lstm/tables/engineering_holdout_predictions/columns.json.gz"
    )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)["columns"]


def build_tape() -> dict[str, object]:
    horizons: dict[str, object] = {}
    step23_report = json.loads(
        (ROOT / "data/sample/models/step23-temporal-deep-validation/report.json").read_text()
    )
    for horizon in HORIZONS:
        columns = load_prediction_columns(horizon)
        card = json.loads((MODELS / horizon / "causal_conv1d_lstm/model-card.json").read_text())
        records = []
        for index, endpoint_time in enumerate(ENDPOINT_TIMES):
            records.append(
                {
                    "decision_id": index + 1,
                    "endpoint_row_id": columns["endpoint_row_id"][index],
                    "endpoint_time_ns": endpoint_time,
                    "feature_cutoff_time_ns": endpoint_time - 1,
                    "available_time_ns": endpoint_time - 1,
                    "calibrated_probability": columns["calibrated_probability"][index],
                    "uncalibrated_probability": columns["uncalibrated_probability"][index],
                    "target": columns["target"][index],
                }
            )
        horizons[horizon] = {
            "training_base_rate": card["training_prevalence"],
            "prediction_table_sha256": step23_report["models"][horizon]["prediction_data_sha256"],
            "records": records,
        }
    return {
        "schema_version": "ml-mpc-prediction-tape-v1",
        "step": 24,
        "research_status": "synthetic_validation_only_non_research",
        "source_dataset": "step23-temporal-deep-validation",
        "horizons": horizons,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tape = build_tape()
    (OUT / "prediction-tapes.json").write_text(canonical_json(tape) + "\n")
    report = subprocess.check_output([str(REPORT_EXE)], text=True)
    json.loads(report)
    (OUT / "report.json").write_text(report)


if __name__ == "__main__":
    main()
