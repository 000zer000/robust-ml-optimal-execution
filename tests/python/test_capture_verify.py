from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from robust_execution.data_capture.models import RawMessageRecord
from robust_execution.data_capture.storage import (
    GzipJsonlSegmentWriter,
    artifact_as_dict,
    write_immutable_gzip_blob,
    write_immutable_json,
)
from robust_execution.data_capture.verify import CaptureVerificationError, verify_capture_manifest


def make_capture(tmp_path: Path) -> Path:
    root = tmp_path / "run"
    writer = GzipJsonlSegmentWriter(root / "raw/segment-000000.jsonl.gz")
    raw = '{"stream":"btcusdt@trade","data":{"e":"trade","s":"BTCUSDT"}}'
    writer.append(
        RawMessageRecord(
            1,
            "run",
            "connection-0000",
            0,
            1,
            2,
            "btcusdt@trade",
            "BTCUSDT",
            "trade",
            hashlib.sha256(raw.encode()).hexdigest(),
            raw,
        )
    )
    artifact = artifact_as_dict(writer.seal(), root)
    config_bytes = b'{"schema_version":1}\n'
    config_artifact = artifact_as_dict(
        write_immutable_gzip_blob(
            root / "metadata/capture-config.json.gz",
            config_bytes,
            content_type="application/json; profile=raw-capture-config-v1",
        ),
        root,
    )
    manifest = {
        "schema_version": 1,
        "step": 12,
        "run_id": "run",
        "data_origin": "live_binance",
        "research_specification_changed": False,
        "paid_data_used": False,
        "software_version": "0.9.0",
        "runtime": {
            "python": "3.13",
            "implementation": "CPython",
            "platform": "test",
            "byteorder": "little",
        },
        "capture_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "status": "pilot_incomplete",
        "actual_duration_seconds": 1.0,
        "pilot_72h_complete": False,
        "total_messages": 1,
        "total_raw_payload_bytes": len(raw.encode()),
        "artifacts": [config_artifact, artifact],
    }
    manifest_path = root / "manifest.json"
    write_immutable_json(manifest_path, manifest)
    write_immutable_json(
        root / "manifest.sha256.json",
        {"sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
    )
    return manifest_path


def test_verify_capture_manifest(tmp_path: Path) -> None:
    result = verify_capture_manifest(make_capture(tmp_path))
    assert result["messages"] == 1
    assert result["pilot_72h_complete"] is False


def test_verify_rejects_tampered_segment(tmp_path: Path) -> None:
    manifest = make_capture(tmp_path)
    segment = manifest.parent / "raw/segment-000000.jsonl.gz"
    segment.write_bytes(segment.read_bytes() + b"tamper")
    with pytest.raises(CaptureVerificationError, match="checksum"):
        verify_capture_manifest(manifest)


def test_verify_rejects_false_completion_claim(tmp_path: Path) -> None:
    manifest_path = make_capture(tmp_path)
    payload = json.loads(manifest_path.read_text())
    payload["pilot_72h_complete"] = True
    payload["status"] = "complete"
    manifest_path.unlink()
    (manifest_path.parent / "manifest.sha256.json").unlink()
    write_immutable_json(manifest_path, payload)
    write_immutable_json(
        manifest_path.parent / "manifest.sha256.json",
        {"sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
    )
    with pytest.raises(CaptureVerificationError, match="72-hour"):
        verify_capture_manifest(manifest_path)
