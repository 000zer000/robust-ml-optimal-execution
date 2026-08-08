#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from robust_execution.historical_replay.tables import read_table
from robust_execution.prediction import (
    load_prediction_feature_config,
    verify_prediction_dataset,
    write_prediction_fixture,
)
from robust_execution.prediction.fixture import validation_fixture

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step21_causal_features_sample.json"
MANIFEST = ROOT / "data/sample/prediction/step21-prediction-validation/dataset-manifest.json"
MUTATION = ROOT / "results/validation/step21/leakage_mutation_report.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    result = verify_prediction_dataset(MANIFEST)
    manifest = json.loads(MANIFEST.read_text())
    if result != {"status": "ok", "rows": 8, "features": 20, "tables": 2}:
        fail("Step 21 dataset verification changed")
    table_map = {item["table_name"]: item for item in manifest["tables"]}
    labels = read_table(MANIFEST.parent, table_map["prediction_labels"]["data_relative_path"])
    positives = {
        suffix: sum(int(row[f"quote_depletion_{suffix}"]) for row in labels)
        for suffix in ("250ms", "1s", "5s")
    }
    if positives != {"250ms": 3, "1s": 3, "5s": 6}:
        fail(f"Step 21 deterministic target oracle changed: {positives}")
    mutation = json.loads(MUTATION.read_text())
    required_true = (
        "future_mutation_same_decision_feature_hash_unchanged",
        "future_mutation_target_changed",
        "post_horizon_mutation_all_rows_unchanged",
        "past_mutation_feature_hash_changed",
        "features_and_labels_physically_separated",
    )
    if not all(mutation.get(key) is True for key in required_true):
        fail("Step 21 leakage mutation report failed")
    if mutation.get("selected_horizon_frozen") is not False:
        fail("Step 21 must not select the primary horizon")
    if mutation.get("research_status") != "synthetic_validation_only_non_research":
        fail("Step 21 research boundary changed")

    config = load_prediction_feature_config(CONFIG)
    events, decisions, coverage = validation_fixture()
    with tempfile.TemporaryDirectory(prefix="step21-rerun-") as temporary:
        rerun_manifest = write_prediction_fixture(
            config, events, decisions, coverage, Path(temporary)
        )
        if rerun_manifest.read_bytes() != MANIFEST.read_bytes():
            fail("Step 21 manifest is not deterministic")
        for relative in (
            "feature-dictionary.json",
            "input-events.json",
            "tables/prediction_features/columns.json.gz",
            "tables/prediction_labels/columns.json.gz",
        ):
            if (rerun_manifest.parent / relative).read_bytes() != (
                MANIFEST.parent / relative
            ).read_bytes():
                fail(f"Step 21 deterministic artifact changed: {relative}")
    print(
        json.dumps(
            {
                "status": "ok",
                "step": 21,
                "rows": 8,
                "features": 20,
                "positives": positives,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
