#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import jsonschema

from robust_execution.data_validation.config import load_data_validation_config
from robust_execution.data_validation.fixture import generate_step13_capture_fixture
from robust_execution.data_validation.validator import validate_capture_data
from robust_execution.data_validation.verify import verify_data_validation_report

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/data/binance_raw_validation.json"
CAPTURE = ROOT / "data/sample/validation_step13/step13-full-day-fixture/manifest.json"
REPORT = ROOT / "results/validation/step13/step13-fixture-validation/validation-report.json"


def canonical_tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    config = load_data_validation_config(CONFIG)
    verification = verify_data_validation_report(REPORT)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    day = report["days"][0]
    if day["structural_status"] != "valid":
        raise SystemExit("committed Step 13 fixture is not structurally valid")
    if day["admission_status"] != "fixture_valid_not_admissible":
        raise SystemExit("synthetic fixture admission boundary was weakened")
    if report["summary"]["admitted_days"] != 0:
        raise SystemExit("synthetic fixture was incorrectly admitted")

    schema_instances = [
        (
            ROOT / "schemas/data/raw-data-validation-config-v1.schema.json",
            CONFIG,
        ),
        (
            ROOT / "schemas/data/raw-data-validation-report-v1.schema.json",
            REPORT,
        ),
        (
            ROOT / "schemas/data/quarantine-manifest-v1.schema.json",
            REPORT.with_name("quarantine-manifest.json"),
        ),
    ]
    for schema_path, instance_path in schema_instances:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)

    with tempfile.TemporaryDirectory(prefix="step13-validation-") as directory:
        temp = Path(directory)
        regenerated_capture = generate_step13_capture_fixture(temp / "capture")
        regenerated_report = validate_capture_data(
            regenerated_capture,
            config,
            temp / "validation",
            validation_id="step13-fixture-validation",
        )
        committed_capture_root = CAPTURE.parent
        regenerated_capture_root = regenerated_capture.parent
        if canonical_tree(committed_capture_root) != canonical_tree(regenerated_capture_root):
            raise SystemExit("Step 13 capture fixture is not deterministic")
        committed_validation_root = REPORT.parent
        regenerated_validation_root = regenerated_report.parent
        if canonical_tree(committed_validation_root) != canonical_tree(regenerated_validation_root):
            raise SystemExit("Step 13 validation output is not deterministic")

    print(
        json.dumps(
            {
                "status": "ok",
                "fixture_structural_status": day["structural_status"],
                "fixture_admission_status": day["admission_status"],
                "admitted_days": verification["admitted_days"],
                "deterministic_regeneration": True,
                "schemas": 3,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
