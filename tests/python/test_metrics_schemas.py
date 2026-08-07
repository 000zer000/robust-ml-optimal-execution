from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]


def test_step17_schemas_and_instances() -> None:
    pairs = [
        (
            ROOT / "schemas/metrics/metrics-contract-v1.schema.json",
            ROOT / "configs/metrics/step17_metrics_validation.json",
        ),
        (
            ROOT / "schemas/metrics/metrics-validation-report-v1.schema.json",
            ROOT / "data/sample/metrics/step17-metrics-validation/report.json",
        ),
        (
            ROOT / "schemas/metrics/metrics-evidence-manifest-v1.schema.json",
            ROOT / "data/sample/metrics/step17-metrics-validation/manifest.json",
        ),
    ]
    for schema_path, instance_path in pairs:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)
