#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import jsonschema

from robust_execution.prediction.simple_model_artifacts import (
    FAMILIES,
    verify_simple_model_fixture,
    write_simple_model_fixture,
)
from robust_execution.prediction.simple_models import load_simple_model_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step22_simple_models_engineering.json"
MANIFEST = ROOT / "data/sample/models/step22-simple-models-validation/dataset-manifest.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    config = load_simple_model_config(CONFIG)
    result = verify_simple_model_fixture(MANIFEST, config)
    manifest_schema = json.loads(
        (ROOT / "schemas/prediction/simple-model-dataset-manifest-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(manifest_schema)
    jsonschema.validate(instance=json.loads(MANIFEST.read_text()), schema=manifest_schema)
    card_schema = json.loads(
        (ROOT / "schemas/prediction/simple-model-card-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(card_schema)
    for horizon in config.candidate_horizons:
        for family in FAMILIES:
            card = json.loads(
                (MANIFEST.parent / "models" / horizon / family / "model-card.json").read_text()
            )
            jsonschema.validate(instance=card, schema=card_schema)
    expected = {"status": "ok", "rows": 800, "models": 12, "horizons": 3}
    if result != expected:
        fail(f"Step 22 verification changed: {result}")
    report = json.loads((MANIFEST.parent / "report.json").read_text())
    if report["research_status"] != "synthetic_validation_only_non_research":
        fail("Step 22 research boundary changed")
    if report["primary_horizon_selected"] or report["final_model_family_selected"]:
        fail("Step 22 must not select the research horizon or final model family")
    if report["locked_research_test_opened"]:
        fail("Step 22 may not open the locked research test")
    if set(report["models"]) != {"250ms", "1s", "5s"}:
        fail("Step 22 horizon set changed")
    for horizon in report["models"].values():
        if set(horizon) != set(FAMILIES):
            fail("Step 22 model-family set changed")
    with (
        tempfile.TemporaryDirectory(prefix="step22-rerun-a-") as first_directory,
        tempfile.TemporaryDirectory(prefix="step22-rerun-b-") as second_directory,
    ):
        first = write_simple_model_fixture(config, Path(first_directory))
        second = write_simple_model_fixture(config, Path(second_directory))
        verify_simple_model_fixture(first, config)
        verify_simple_model_fixture(second, config)

        def nonbinary_hashes(manifest_path: Path) -> dict[str, str]:
            fixture_manifest = json.loads(manifest_path.read_text())
            return {
                item["relative_path"]: item["sha256"]
                for item in fixture_manifest["artifacts"]
                if item["kind"] != "trusted_pickle_model"
            }

        first_report = (first.parent / "report.json").read_bytes()
        if first_report != (second.parent / "report.json").read_bytes():
            fail("Step 22 semantic report is not deterministic within this environment")
        if nonbinary_hashes(first) != nonbinary_hashes(second):
            fail("Step 22 non-binary artifacts are not deterministic within this environment")

        # Fitted floating-point artifacts can differ across CPUs and BLAS kernels even when the
        # OS, architecture, Python and direct package versions match. The committed fixture is
        # integrity- and prediction-verified above; regeneration is required to be byte-stable
        # across two independent runs on the actual host executing this validator.
    print(json.dumps({"status": "ok", "step": 22, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
