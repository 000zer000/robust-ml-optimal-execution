from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, Callable

import pytest

from robust_execution.queue_models.verify import (
    QueueModelVerificationError,
    verify_queue_model_report,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/sample/queue_models/step16-queue-model-validation"


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "fixture"
    shutil.copytree(SOURCE, target)
    return target / "manifest.json"


def test_verify_queue_model_report() -> None:
    result = verify_queue_model_report(SOURCE / "manifest.json")
    assert result["scenario_count"] == 5
    assert result["sensitivity_count"] == 9
    assert result["all_exact_results_bracketed"]
    assert not result["historical_exact_fifo_reconstructed"]


def rewrite_json(path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(step=15),
        lambda value: value.update(research_status="research"),
        lambda value: value.update(report_sha256="0" * 64),
        lambda value: value.update(extra=True),
        lambda value: value.update(artifacts=[]),
        lambda value: value["artifacts"][0].update(path="../report.json"),
        lambda value: value["artifacts"][0].update(bytes=0),
    ],
)
def test_manifest_tampering_is_rejected(tmp_path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    manifest = copy_fixture(tmp_path)
    rewrite_json(manifest, mutation)
    with pytest.raises(QueueModelVerificationError):
        verify_queue_model_report(manifest)


def test_artifact_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = copy_fixture(tmp_path)
    (manifest.parent / "report.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(QueueModelVerificationError):
        verify_queue_model_report(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(historical_exact_fifo_reconstructed=True),
        lambda value: value.update(ghost_small_agent_assumption=False),
        lambda value: value.update(trade_through_rule_passed=False),
        lambda value: value.update(no_fill_from_cancellation_only_passed=False),
        lambda value: value.update(deterministic=False),
        lambda value: value.update(scenarios=[]),
        lambda value: value["scenarios"][0].update(optimistic_fill_lots=-1),
        lambda value: value["scenarios"][0].update(optimistic_fill_lots=0),
        lambda value: value["scenarios"][0].update(exact_within_model_bounds=False),
        lambda value: value["scenarios"][0].update(scenario_id="mixed_cancellation"),
        lambda value: value.update(sensitivity=[]),
        lambda value: value["sensitivity"][0].update(assumption="invalid"),
        lambda value: value["sensitivity"][0].update(estimated_fill_lots=-1),
        lambda value: value["sensitivity"][0].update(additional_initial_ahead_bps=5000),
    ],
)
def test_report_semantic_tampering_is_rejected(tmp_path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    manifest = copy_fixture(tmp_path)
    report = manifest.parent / "report.json"
    rewrite_json(report, mutation)
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    import hashlib

    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    metadata["report_sha256"] = digest
    for item in metadata["artifacts"]:
        if item["path"] == "report.json":
            item["sha256"] = digest
            item["bytes"] = report.stat().st_size
    manifest.write_text(json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(QueueModelVerificationError):
        verify_queue_model_report(manifest)


def test_csv_row_count_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = copy_fixture(tmp_path)
    csv_path = manifest.parent / "sensitivity.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    csv_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    import hashlib

    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    for item in metadata["artifacts"]:
        if item["path"] == "sensitivity.csv":
            item["sha256"] = digest
            item["bytes"] = csv_path.stat().st_size
    manifest.write_text(json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with pytest.raises(QueueModelVerificationError):
        verify_queue_model_report(manifest)
