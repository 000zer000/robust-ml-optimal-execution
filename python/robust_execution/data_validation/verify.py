"""Independent verification of Step 13 outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class DataValidationVerificationError(RuntimeError):
    """Raised when a Step 13 report or quarantine artifact is inconsistent."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationVerificationError(f"cannot read {path.name}: {exc}") from exc


def _verify_digest(path: Path) -> str:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = _read_json(path.with_name(path.stem + ".sha256.json"))
    if expected != {"sha256": actual}:
        raise DataValidationVerificationError(f"digest mismatch for {path.name}")
    return actual


def verify_data_validation_report(report_path: Path) -> dict[str, Any]:
    report = _read_json(report_path)
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("step") != 13:
        raise DataValidationVerificationError("unsupported Step 13 report")
    if report.get("research_specification_changed") is not False:
        raise DataValidationVerificationError("report claims the specification changed")
    if report.get("missing_events_repaired") is not False:
        raise DataValidationVerificationError("primary historical repair is forbidden")
    if report.get("source_capture_verified") is not True:
        raise DataValidationVerificationError("source capture was not independently verified")
    report_digest = _verify_digest(report_path)
    quarantine_path = report_path.with_name("quarantine-manifest.json")
    quarantine = _read_json(quarantine_path)
    if not isinstance(quarantine, dict) or quarantine.get("validation_id") != report.get("validation_id"):
        raise DataValidationVerificationError("quarantine manifest does not match report")
    quarantine_digest = _verify_digest(quarantine_path)
    days = report.get("days")
    if not isinstance(days, list):
        raise DataValidationVerificationError("days must be an array")
    admitted = [item for item in days if isinstance(item, dict) and item.get("admission_status") == "admitted"]
    for item in admitted:
        if item.get("structural_status") != "valid" or item.get("reasons"):
            raise DataValidationVerificationError("admitted day has unresolved validation reasons")
    summary = report.get("summary")
    if not isinstance(summary, dict) or summary.get("admitted_days") != len(admitted):
        raise DataValidationVerificationError("summary admitted_days is inconsistent")
    return {
        "status": "ok",
        "validation_id": report.get("validation_id"),
        "days": len(days),
        "admitted_days": len(admitted),
        "report_sha256": report_digest,
        "quarantine_sha256": quarantine_digest,
    }
