#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.data_capture.config import load_capture_config  # noqa: E402
from robust_execution.data_capture.offline_fixture import write_offline_fixture  # noqa: E402
from robust_execution.data_capture.verify import verify_capture_manifest  # noqa: E402
from robust_execution.specification import verify_specification_lock  # noqa: E402


def hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def deterministic_payload_hashes(root: Path) -> dict[str, str]:
    environment_specific = {
        "manifest.json",
        "manifest.sha256.json",
        "metadata/runtime.json.gz",
    }
    return {
        relative: digest
        for relative, digest in hashes(root).items()
        if relative not in environment_specific
    }


def normalized_manifest(path: Path) -> dict[str, object]:
    """Remove only host provenance and its derived size totals from a fixture manifest."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {
        "python",
        "implementation",
        "platform",
        "byteorder",
    }:
        raise RuntimeError("Step 12 runtime provenance is missing or malformed")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("Step 12 artifacts are missing")
    runtime_artifacts = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("relative_path") == "metadata/runtime.json.gz"
    ]
    if len(runtime_artifacts) != 1:
        raise RuntimeError("Step 12 runtime artifact must appear exactly once")
    runtime_bytes = runtime_artifacts[0].get("compressed_bytes")
    runtime_raw_bytes = runtime_artifacts[0].get("uncompressed_bytes")
    total_bytes = manifest.get("total_compressed_bytes")
    total_raw_bytes = manifest.get("total_uncompressed_bytes")
    if not all(
        isinstance(value, int)
        for value in (runtime_bytes, runtime_raw_bytes, total_bytes, total_raw_bytes)
    ):
        raise RuntimeError("Step 12 runtime byte accounting is malformed")
    manifest["runtime"] = "host-specific-provenance-verified-separately"
    manifest["artifacts"] = [item for item in artifacts if item not in runtime_artifacts]
    manifest["total_compressed_bytes"] = total_bytes - runtime_bytes
    manifest["total_uncompressed_bytes"] = total_raw_bytes - runtime_raw_bytes
    return manifest


def validate_schema(schema_path: Path, instance_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(instance)


def main() -> int:
    failures = verify_specification_lock(ROOT)
    if failures:
        raise RuntimeError(f"specification lock failed: {failures}")

    config_path = ROOT / "configs/data/binance_capture_pilot.json"
    sample_manifest = ROOT / "data/sample/capture/step12-offline-fixture/manifest.json"
    validate_schema(ROOT / "schemas/data/raw-capture-config-v1.schema.json", config_path)
    validate_schema(ROOT / "schemas/data/raw-capture-manifest-v1.schema.json", sample_manifest)
    config = load_capture_config(config_path)
    sample_result = verify_capture_manifest(sample_manifest)
    if sample_result["pilot_72h_complete"]:
        raise RuntimeError("synthetic fixture must not satisfy the live pilot")

    with tempfile.TemporaryDirectory(prefix="step12-fixture-") as directory:
        regenerated_manifest = asyncio.run(write_offline_fixture(config, Path(directory)))
        if deterministic_payload_hashes(sample_manifest.parent) != deterministic_payload_hashes(
            regenerated_manifest.parent
        ):
            raise RuntimeError("committed Step 12 fixture payload is not byte reproducible")
        if normalized_manifest(sample_manifest) != normalized_manifest(regenerated_manifest):
            raise RuntimeError(
                "committed Step 12 fixture manifest is not semantically reproducible"
            )

    network_path = ROOT / "results/validation/step12/network_check.json"
    network = json.loads(network_path.read_text(encoding="utf-8"))
    if set(network) != {"rest", "websocket"}:
        raise RuntimeError("network evidence must cover REST and WebSocket hosts")
    if any(item.get("status") not in {"resolved", "failed"} for item in network.values()):
        raise RuntimeError("network evidence contains an invalid status")

    live_manifest = (
        ROOT / "results/validation/step12/live_attempt_data/live-smoke-20260806b/manifest.json"
    )
    live_result = verify_capture_manifest(live_manifest)
    live_payload = json.loads(live_manifest.read_text(encoding="utf-8"))
    if live_payload["data_origin"] != "live_binance":
        raise RuntimeError("live attempt is not labelled live_binance")
    if live_result["pilot_72h_complete"]:
        raise RuntimeError("short smoke attempt must not claim 72-hour completion")

    result = {
        "status": "conditional_pass",
        "engineering_validation": "pass",
        "live_72h_pilot": "pending",
        "specification_lock": "7/7",
        "fixture_files": len(hashes(sample_manifest.parent)),
        "fixture_messages": sample_result["messages"],
        "live_smoke_status": live_payload["status"],
        "live_smoke_messages": live_payload["total_messages"],
        "network": {key: value["status"] for key, value in network.items()},
    }
    output = ROOT / "results/validation/step12/step12_validation.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
