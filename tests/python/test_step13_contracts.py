from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]


def test_step13_schemas_and_committed_artifacts() -> None:
    base = ROOT / "results/validation/step13/step13-fixture-validation"
    pairs = [
        (
            ROOT / "schemas/data/raw-data-validation-config-v1.schema.json",
            ROOT / "configs/data/binance_raw_validation.json",
        ),
        (
            ROOT / "schemas/data/raw-data-validation-report-v1.schema.json",
            base / "validation-report.json",
        ),
        (
            ROOT / "schemas/data/day-admission-decision-v1.schema.json",
            base / "validation-report.json",
            "days",
        ),
        (
            ROOT / "schemas/data/quarantine-manifest-v1.schema.json",
            base / "quarantine-manifest.json",
        ),
    ]
    for item in pairs:
        schema = json.loads(item[0].read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        instance = json.loads(item[1].read_text())
        if len(item) == 3:
            for day in instance[item[2]]:
                jsonschema.Draft202012Validator(schema).validate(day)
        else:
            jsonschema.Draft202012Validator(schema).validate(instance)
