"""Independent verification of Step 12 capture artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from robust_execution.data_capture.storage import StorageError, verify_segment


class CaptureVerificationError(RuntimeError):
    """Raised when a capture manifest or referenced artifact is inconsistent."""


def verify_capture_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureVerificationError(f"cannot read capture manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise CaptureVerificationError("unsupported capture manifest")
    if manifest.get("step") != 12 or manifest.get("research_specification_changed") is not False:
        raise CaptureVerificationError("capture governance fields are invalid")
    if manifest.get("paid_data_used") is not False:
        raise CaptureVerificationError("Step 12 self-capture must not record paid data")

    digest_path = manifest_path.with_name("manifest.sha256.json")
    try:
        digest_payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureVerificationError(f"cannot read manifest digest: {exc}") from exc
    actual_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if digest_payload != {"sha256": actual_manifest_digest}:
        raise CaptureVerificationError("manifest digest mismatch")

    software_version = manifest.get("software_version")
    runtime = manifest.get("runtime")
    if not isinstance(software_version, str) or not software_version:
        raise CaptureVerificationError("capture software_version is missing")
    if not isinstance(runtime, dict) or not runtime:
        raise CaptureVerificationError("capture runtime metadata is missing")

    root = manifest_path.parent
    artifact_records = 0
    config_digest_verified = False
    for artifact in manifest.get("artifacts", []):
        relative = artifact.get("relative_path")
        if not isinstance(relative, str):
            raise CaptureVerificationError("artifact path is missing")
        path = root / relative
        if not path.is_file():
            raise CaptureVerificationError(f"missing artifact: {relative}")
        compressed = path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != artifact.get("sha256"):
            raise CaptureVerificationError(f"artifact checksum mismatch: {relative}")
        if len(compressed) != artifact.get("compressed_bytes"):
            raise CaptureVerificationError(f"artifact size mismatch: {relative}")
        if path.name == "capture-config.json.gz":
            import gzip

            config_bytes = gzip.decompress(compressed)
            if hashlib.sha256(config_bytes).hexdigest() != manifest.get("capture_config_sha256"):
                raise CaptureVerificationError("capture configuration digest mismatch")
            config_digest_verified = True
        if "segment-" in path.name:
            try:
                count = verify_segment(path)
            except StorageError as exc:
                raise CaptureVerificationError(str(exc)) from exc
            if count != artifact.get("record_count"):
                raise CaptureVerificationError(f"segment record count mismatch: {relative}")
            artifact_records += count
    if artifact_records != manifest.get("total_messages"):
        raise CaptureVerificationError("manifest total_messages does not match raw segments")
    if manifest.get("artifacts") and not config_digest_verified:
        raise CaptureVerificationError("capture configuration artifact is missing")
    origin = manifest.get("data_origin")
    if origin not in {"live_binance", "synthetic_transport_fixture"}:
        raise CaptureVerificationError("capture data_origin is invalid")
    complete = bool(manifest.get("pilot_72h_complete"))
    if complete and origin != "live_binance":
        raise CaptureVerificationError("synthetic fixture cannot satisfy the live 72-hour pilot")
    if complete and (
        manifest.get("status") != "complete"
        or float(manifest.get("actual_duration_seconds", 0)) < 259200
    ):
        raise CaptureVerificationError("72-hour completion claim is unsupported")
    return {
        "status": "ok",
        "run_id": manifest.get("run_id"),
        "messages": artifact_records,
        "artifacts": len(manifest.get("artifacts", [])),
        "pilot_72h_complete": complete,
        "manifest_sha256": actual_manifest_digest,
    }
