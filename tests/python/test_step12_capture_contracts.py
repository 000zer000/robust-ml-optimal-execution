from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
from scripts.validate_step12_capture import normalized_manifest

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


def test_step12_manifest_normalization_removes_all_runtime_derived_sizes(
    tmp_path: Path,
) -> None:
    committed = json.loads(
        (ROOT / "data/sample/capture/step12-offline-fixture/manifest.json").read_text()
    )
    other_host = deepcopy(committed)
    other_host["runtime"] = {
        "python": "3.11.15",
        "implementation": "CPython",
        "platform": "Linux-6.11.0-x86_64-with-glibc2.39",
        "byteorder": "little",
    }
    runtime = next(
        item
        for item in other_host["artifacts"]
        if item["relative_path"] == "metadata/runtime.json.gz"
    )
    runtime["compressed_bytes"] += 13
    runtime["uncompressed_bytes"] += 29
    runtime["sha256"] = "0" * 64
    other_host["total_compressed_bytes"] += 13
    other_host["total_uncompressed_bytes"] += 29

    committed_path = tmp_path / "committed.json"
    other_host_path = tmp_path / "other-host.json"
    committed_path.write_text(json.dumps(committed))
    other_host_path.write_text(json.dumps(other_host))

    assert normalized_manifest(committed_path) == normalized_manifest(other_host_path)
