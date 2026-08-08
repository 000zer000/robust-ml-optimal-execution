#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution import __version__  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/sample/queue_models")
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args()
    executable = args.executable or native_executable(ROOT, "robust_execution_queue_demo")
    target = args.output_root / "step16-queue-model-validation"
    if target.exists():
        raise SystemExit(f"Step 16 fixture output already exists: {target}")
    target.mkdir(parents=True)
    completed = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    report = json.loads(completed.stdout)
    report_path = target / "report.json"
    write_json(report_path, report)

    scenario_path = target / "scenario-comparison.csv"
    with scenario_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario_id",
                "exact_fifo_fill_lots",
                "optimistic_fill_lots",
                "central_fill_lots",
                "pessimistic_fill_lots",
                "exact_within_model_bounds",
                "model_ordering_valid",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report["scenarios"])

    sensitivity_path = target / "sensitivity.csv"
    with sensitivity_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario_id",
                "assumption",
                "additional_initial_ahead_bps",
                "estimated_fill_lots",
                "estimated_ahead_after_events_lots",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report["sensitivity"])

    artifacts = []
    for path in (report_path, scenario_path, sensitivity_path):
        artifacts.append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest = {
        "schema_version": "queue-model-evidence-manifest-v1",
        "step": 16,
        "report_id": "step16-queue-model-validation",
        "software_version": __version__,
        "artifacts": artifacts,
        "report_sha256": sha256(report_path),
        "research_status": "synthetic_validation_only_non_research",
    }
    write_json(target / "manifest.json", manifest)
    print(target / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
