#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.metrics import verify_metrics_evidence  # noqa: E402


def main() -> int:
    contract_path = ROOT / "configs/metrics/step17_metrics_validation.json"
    fixture = ROOT / "data/sample/metrics/step17-metrics-validation"
    manifest_path = fixture / "manifest.json"
    schema_pairs = [
        (ROOT / "schemas/metrics/metrics-contract-v1.schema.json", contract_path),
        (
            ROOT / "schemas/metrics/metrics-validation-report-v1.schema.json",
            fixture / "report.json",
        ),
        (ROOT / "schemas/metrics/metrics-evidence-manifest-v1.schema.json", manifest_path),
    ]
    for schema_path, instance_path in schema_pairs:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["accounting"]["require_complete_parent_for_final_shortfall"] is not True:
        raise SystemExit("Step 17 completion requirement was weakened")
    if contract["tail_risk"]["require_independent_episode_audit"] is not True:
        raise SystemExit("Step 17 audit requirement was weakened")
    if contract["performance"]["benchmark_claims_allowed"] is not False:
        raise SystemExit("Step 17 synthetic fixture cannot make performance claims")

    committed = verify_metrics_evidence(manifest_path)
    executable = native_executable(ROOT, "robust_execution_metrics_demo")
    completed = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    if json.loads(completed.stdout) != json.loads(
        (fixture / "report.json").read_text(encoding="utf-8")
    ):
        raise SystemExit("Step 17 C++ metrics demo differs from committed report")

    with tempfile.TemporaryDirectory(prefix="step17-metrics-") as temporary:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/generate_step17_fixture.py"),
                "--output-root",
                temporary,
                "--executable",
                str(executable),
            ],
            check=True,
            cwd=ROOT,
        )
        regenerated = Path(temporary) / "step17-metrics-validation"
        for relative in (
            "manifest.json",
            "report.json",
            "episode-metrics.csv",
            "inventory-trajectory.csv",
            "tail-risk.csv",
        ):
            if (fixture / relative).read_bytes() != (regenerated / relative).read_bytes():
                raise SystemExit(f"Step 17 artifact is not deterministic: {relative}")
        if verify_metrics_evidence(regenerated / "manifest.json") != committed:
            raise SystemExit("Step 17 verification result changed after regeneration")
    print(json.dumps(committed, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
