#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import sys
import tempfile
from pathlib import Path

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
    with (
        tempfile.TemporaryDirectory(prefix="step23-rerun-a-") as first_directory,
        tempfile.TemporaryDirectory(prefix="step23-rerun-b-") as second_directory,
    ):
        first = write_temporal_model_fixture(config, Path(first_directory))
        second = write_temporal_model_fixture(config, Path(second_directory))
        verify_temporal_model_fixture(first, config)
        verify_temporal_model_fixture(second, config)

        def artifact_hashes(manifest_path: Path) -> dict[str, str]:
            fixture_manifest = json.loads(manifest_path.read_text())
            return {item["relative_path"]: item["sha256"] for item in fixture_manifest["artifacts"]}

        first_report = (first.parent / "report.json").read_bytes()
        if artifact_hashes(first) != artifact_hashes(second):
            fail("Step 23 semantic artifacts are not deterministic within this environment")
        if first_report != (second.parent / "report.json").read_bytes():
            fail("Step 23 report is not deterministic within this environment")

        # Canonical fixture bytes are produced on Linux x86-64; other platforms verify the
        # committed model within a strict numeric tolerance and prove local repeatability.
        canonical_platform = (
            platform.system() == "Linux"
            and platform.machine() == "x86_64"
            and sys.version_info[:2] == (3, 13)
        )
        if canonical_platform and artifact_hashes(first) != artifact_hashes(MANIFEST):
            fail("Step 23 canonical semantic artifacts changed on a clean rerun")
        if canonical_platform and first_report != (MANIFEST.parent / "report.json").read_bytes():
            fail("Step 23 canonical report changed on a clean rerun")
    print(json.dumps({"step": 23, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
