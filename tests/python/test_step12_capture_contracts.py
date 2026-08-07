from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from robust_execution.data_capture.verify import verify_capture_manifest


ROOT = Path(__file__).resolve().parents[2]


def test_step12_config_and_manifest_schemas() -> None:
    pairs = [
        (
            ROOT / "schemas/data/raw-capture-config-v1.schema.json",
            ROOT / "configs/data/binance_capture_pilot.json",
        ),
        (
            ROOT / "schemas/data/raw-capture-manifest-v1.schema.json",
            ROOT / "data/sample/capture/step12-offline-fixture/manifest.json",
        ),
    ]
    for schema_path, instance_path in pairs:
        schema = json.loads(schema_path.read_text())
        instance = json.loads(instance_path.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_committed_step12_fixture_verifies_and_is_not_live() -> None:
    manifest = ROOT / "data/sample/capture/step12-offline-fixture/manifest.json"
    result = verify_capture_manifest(manifest)
    payload = json.loads(manifest.read_text())
    assert result["messages"] == 6
    assert payload["data_origin"] == "synthetic_transport_fixture"
    assert payload["pilot_72h_complete"] is False
    assert payload["publication"]["raw_market_data_public"] is False
