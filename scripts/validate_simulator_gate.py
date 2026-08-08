#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "validation" / "simulator-validation-report-v1.schema.json"
FIXTURE = ROOT / "data" / "sample" / "validation"
BINARY = native_executable(ROOT, "robust_execution_validation_demo")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    report = json.loads((FIXTURE / "report.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)

    if report["decision"] != "pass":
        raise RuntimeError("committed Gate B report is not a pass")
    if len(report["checks"]) != 7 or not all(item["passed"] for item in report["checks"]):
        raise RuntimeError("Gate B check set is incomplete or contains a failure")
    if len(report["sensitivities"]) != 4 or not all(
        item["passed"] for item in report["sensitivities"]
    ):
        raise RuntimeError("Gate B sensitivity set is incomplete or contains a failure")
    expected_counts = {
        "generated_seed_count": 64,
        "generated_step_count": 16_384,
        "differential_seed_count": 32,
        "differential_command_count": 64_000,
        "mutation_case_count": 2_048,
    }
    for key, expected in expected_counts.items():
        if report[key] != expected:
            raise RuntimeError(f"unexpected Gate B count for {key}: {report[key]}")

    expected_hash = (FIXTURE / "report.json.sha256").read_text(encoding="utf-8").split()[0]
    if sha256(FIXTURE / "report.json") != expected_hash:
        raise RuntimeError("committed Gate B report hash mismatch")

    summary_lines = set((FIXTURE / "summary.txt").read_text(encoding="utf-8").splitlines())
    required = {
        "step=10",
        "gate_id=gate-b",
        "decision=pass",
        "checks_passed=7/7",
        "sensitivities_passed=4/4",
        "generated_seeds=64",
        "generated_steps=16384",
        "differential_seeds=32",
        "differential_commands=64000",
        "mutation_cases=2048",
    }
    if not required.issubset(summary_lines):
        raise RuntimeError("Gate B summary is missing required evidence fields")

    with tempfile.TemporaryDirectory(prefix="re-step10-") as temp:
        output_dir = Path(temp)
        result = subprocess.run(
            [str(BINARY), "--output-dir", str(output_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.encode() != (FIXTURE / "summary.txt").read_bytes():
            raise RuntimeError("Gate B text summary is not byte deterministic")
        if (output_dir / "report.json").read_bytes() != (FIXTURE / "report.json").read_bytes():
            raise RuntimeError("Gate B JSON report is not byte deterministic")

    invalid = dict(report)
    invalid["decision"] = "unsupported"
    if not list(Draft202012Validator(schema).iter_errors(invalid)):
        raise RuntimeError("negative report-schema control unexpectedly passed")

    print(f"simulator Gate B: PASS (7 checks, 4 sensitivities, report {expected_hash[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
