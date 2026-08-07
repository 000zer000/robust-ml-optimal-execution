#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import jsonschema

from robust_execution.prediction.temporal_model_artifacts import (
    FAMILY,
    verify_temporal_model_fixture,
    write_temporal_model_fixture,
)
from robust_execution.prediction.temporal_models import load_temporal_model_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step23_temporal_deep_engineering.json"
MANIFEST = ROOT / "data/sample/models/step23-temporal-deep-validation/dataset-manifest.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    config = load_temporal_model_config(CONFIG)
    result = verify_temporal_model_fixture(MANIFEST, config)
    manifest_schema = json.loads(
        (ROOT / "schemas/prediction/temporal-model-dataset-manifest-v1.schema.json").read_text()
    )
    card_schema = json.loads(
        (ROOT / "schemas/prediction/temporal-model-card-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(manifest_schema)
    jsonschema.Draft202012Validator.check_schema(card_schema)
    jsonschema.validate(instance=json.loads(MANIFEST.read_text()), schema=manifest_schema)
    for horizon in config.candidate_horizons:
        card_path = MANIFEST.parent / "models" / horizon / FAMILY / "model-card.json"
        jsonschema.validate(instance=json.loads(card_path.read_text()), schema=card_schema)
    expected = {"status": "ok", "source_rows": 4800, "sequences": 2000, "models": 3, "horizons": 3}
    if result != expected:
        fail(f"Step 23 verification changed: {result}")
    report = json.loads((MANIFEST.parent / "report.json").read_text())
    if report["research_status"] != "synthetic_validation_only_non_research":
        fail("Step 23 research boundary changed")
    forbidden = (
        "primary_horizon_selected",
        "final_model_family_selected",
        "engineering_holdout_used_for_selection",
        "decision_proxy_used_for_selection",
        "locked_research_test_opened",
        "step24_controller_integrated",
    )
    if any(report[field] for field in forbidden):
        fail("Step 23 opened a forbidden selection/test/controller path")
    if report["architecture"] != FAMILY or report["architecture_count"] != 1:
        fail("Step 23 must contain exactly one serious temporal architecture")
    with tempfile.TemporaryDirectory(prefix="step23-rerun-") as temporary:
        rerun = write_temporal_model_fixture(config, Path(temporary))
        verify_temporal_model_fixture(rerun, config)
        committed_manifest = json.loads(MANIFEST.read_text())
        rerun_manifest = json.loads(rerun.read_text())
        committed = {
            item["relative_path"]: item["sha256"] for item in committed_manifest["artifacts"]
        }
        repeated = {
            item["relative_path"]: item["sha256"] for item in rerun_manifest["artifacts"]
        }
        if committed != repeated:
            fail("Step 23 deterministic semantic artifacts changed on a clean rerun")
        if (rerun.parent / "report.json").read_bytes() != (
            MANIFEST.parent / "report.json"
        ).read_bytes():
            fail("Step 23 report is not byte-deterministic")
    print(json.dumps({"step": 23, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
