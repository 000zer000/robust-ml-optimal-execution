from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_schemas_and_configs() -> None:
    schema_dir = ROOT / "schemas" / "synthetic"
    config_schema = json.loads(
        (schema_dir / "synthetic-market-config-v1.schema.json").read_text(encoding="utf-8")
    )
    manifest_schema = json.loads(
        (schema_dir / "synthetic-market-manifest-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(config_schema)
    Draft202012Validator.check_schema(manifest_schema)
    validator = Draft202012Validator(config_schema)
    configs = sorted((ROOT / "configs" / "stress_tests").glob("synthetic_*.json"))
    assert len(configs) >= 2
    for path in configs:
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_synthetic_fixture_hash_and_claim_boundary() -> None:
    fixture = ROOT / "data" / "sample" / "synthetic"
    manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas" / "synthetic" / "synthetic-market-manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(manifest)
    assert manifest["calibration_status"] == "not_calibrated_step9"
    assert manifest["scenario_class"] == "adversarial_stress"
    assert manifest["tape_sha256"] == hashlib.sha256((fixture / "tape.txt").read_bytes()).hexdigest()
    assert len(manifest["limitations"]) >= 4
