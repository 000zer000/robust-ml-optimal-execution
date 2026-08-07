"""Independent verification for committed Step 16 queue-model evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


class QueueModelVerificationError(ValueError):
    """Raised when queue-model evidence is malformed or tampered."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueueModelVerificationError(f"JSON object required: {path}")
    return value


def verify_queue_model_report(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    expected_keys = {
        "schema_version",
        "step",
        "report_id",
        "software_version",
        "artifacts",
        "report_sha256",
        "research_status",
    }
    if set(manifest) != expected_keys:
        raise QueueModelVerificationError("queue-model manifest keys differ")
    if manifest["schema_version"] != "queue-model-evidence-manifest-v1" or manifest["step"] != 16:
        raise QueueModelVerificationError("queue-model manifest identity is invalid")
    if manifest["research_status"] != "synthetic_validation_only_non_research":
        raise QueueModelVerificationError("queue-model evidence cannot claim historical research status")
    root = manifest_path.parent
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise QueueModelVerificationError("queue-model manifest must contain three artifacts")
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            raise QueueModelVerificationError("queue-model artifact entry is invalid")
        relative = item["path"]
        if not isinstance(relative, str) or relative in seen or relative.startswith("/") or ".." in Path(relative).parts:
            raise QueueModelVerificationError("queue-model artifact path is invalid")
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
            raise QueueModelVerificationError(f"queue-model artifact verification failed: {relative}")
    if seen != {"report.json", "scenario-comparison.csv", "sensitivity.csv"}:
        raise QueueModelVerificationError("queue-model artifact set differs")

    report_path = root / "report.json"
    report = _load_json(report_path)
    if _sha256(report_path) != manifest["report_sha256"]:
        raise QueueModelVerificationError("report_sha256 differs")
    if report.get("schema_version") != "queue-model-validation-v1" or report.get("step") != 16:
        raise QueueModelVerificationError("queue-model report identity is invalid")
    if report.get("historical_exact_fifo_reconstructed") is not False:
        raise QueueModelVerificationError("historical exact FIFO claim is forbidden")
    if report.get("ghost_small_agent_assumption") is not True:
        raise QueueModelVerificationError("ghost small-agent boundary must be explicit")
    for key in ("trade_through_rule_passed", "no_fill_from_cancellation_only_passed", "deterministic"):
        if report.get(key) is not True:
            raise QueueModelVerificationError(f"queue-model gate failed: {key}")
    scenarios = report.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 5:
        raise QueueModelVerificationError("queue-model scenario matrix is incomplete")
    required_scenarios = {
        "no_cancellation",
        "cancellation_ahead",
        "cancellation_behind",
        "mixed_cancellation",
        "addition_only",
    }
    scenario_ids: set[str] = set()
    for row in scenarios:
        if not isinstance(row, dict):
            raise QueueModelVerificationError("queue-model scenario row must be an object")
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id in scenario_ids:
            raise QueueModelVerificationError("queue-model scenario IDs must be unique")
        scenario_ids.add(scenario_id)
        values = [
            row.get("optimistic_fill_lots"),
            row.get("central_fill_lots"),
            row.get("pessimistic_fill_lots"),
            row.get("exact_fifo_fill_lots"),
        ]
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise QueueModelVerificationError("queue-model fill values must be non-negative integers")
        optimistic, central, pessimistic, exact = values
        if not optimistic >= central >= pessimistic:
            raise QueueModelVerificationError("queue-model ordering is violated")
        if not optimistic >= exact >= pessimistic:
            raise QueueModelVerificationError("exact FIFO result is outside model bounds")
        if row.get("exact_within_model_bounds") is not True or row.get("model_ordering_valid") is not True:
            raise QueueModelVerificationError("queue-model scenario gate flag is false")
    if scenario_ids != required_scenarios:
        raise QueueModelVerificationError("queue-model required scenarios differ")

    sensitivity = report.get("sensitivity")
    if not isinstance(sensitivity, list) or len(sensitivity) != 9:
        raise QueueModelVerificationError("queue-model sensitivity matrix must have nine rows")
    combinations: set[tuple[str, int]] = set()
    for row in sensitivity:
        if not isinstance(row, dict) or row.get("scenario_id") != "mixed_cancellation":
            raise QueueModelVerificationError("queue-model sensitivity row is invalid")
        assumption = row.get("assumption")
        buffer = row.get("additional_initial_ahead_bps")
        if assumption not in {"optimistic", "central", "pessimistic"} or buffer not in {0, 2500, 5000}:
            raise QueueModelVerificationError("queue-model sensitivity coordinates differ")
        if (assumption, buffer) in combinations:
            raise QueueModelVerificationError("duplicate queue-model sensitivity coordinate")
        combinations.add((assumption, buffer))
        for key in ("estimated_fill_lots", "estimated_ahead_after_events_lots"):
            value = row.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise QueueModelVerificationError("queue-model sensitivity values are invalid")
    for assumption in ("optimistic", "central", "pessimistic"):
        rows = sorted(
            (row for row in sensitivity if row["assumption"] == assumption),
            key=lambda item: item["additional_initial_ahead_bps"],
        )
        fills = [row["estimated_fill_lots"] for row in rows]
        ahead = [row["estimated_ahead_after_events_lots"] for row in rows]
        if fills != sorted(fills, reverse=True) or ahead != sorted(ahead):
            raise QueueModelVerificationError("hidden-ahead sensitivity is not monotonic")

    with (root / "scenario-comparison.csv").open(newline="", encoding="utf-8") as handle:
        scenario_csv = list(csv.DictReader(handle))
    with (root / "sensitivity.csv").open(newline="", encoding="utf-8") as handle:
        sensitivity_csv = list(csv.DictReader(handle))
    if len(scenario_csv) != len(scenarios) or len(sensitivity_csv) != len(sensitivity):
        raise QueueModelVerificationError("queue-model CSV row counts differ from JSON")
    return {
        "report_id": manifest["report_id"],
        "scenario_count": len(scenarios),
        "sensitivity_count": len(sensitivity),
        "all_exact_results_bracketed": True,
        "historical_exact_fifo_reconstructed": False,
        "research_status": manifest["research_status"],
        "report_sha256": manifest["report_sha256"],
    }
