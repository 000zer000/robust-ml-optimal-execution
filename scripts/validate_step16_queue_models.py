#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.queue_models import (  # noqa: E402
    load_queue_model_contract,
    verify_queue_model_report,
)


def main() -> int:
    contract_path = ROOT / "configs/data/aggregate_queue_models.json"
    manifest_path = ROOT / "data/sample/queue_models/step16-queue-model-validation/manifest.json"
    contract = load_queue_model_contract(contract_path)
    if tuple(model.assumption for model in contract.models) != (
        "optimistic",
        "central",
        "pessimistic",
    ):
        raise SystemExit("Step 16 model ordering differs")

    schemas = [
        (ROOT / "schemas/queue_models/queue-model-contract-v1.schema.json", contract_path),
        (
            ROOT / "schemas/queue_models/queue-model-validation-report-v1.schema.json",
            manifest_path.parent / "report.json",
        ),
        (
            ROOT / "schemas/queue_models/queue-model-evidence-manifest-v1.schema.json",
            manifest_path,
        ),
    ]
    for schema_path, instance_path in schemas:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)

    committed = verify_queue_model_report(manifest_path)
    executable = ROOT / "build/gcc-debug/robust_execution_queue_demo"
    completed = subprocess.run([str(executable)], check=True, capture_output=True)
    if json.loads(completed.stdout) != json.loads((manifest_path.parent / "report.json").read_text(encoding="utf-8")):
        raise SystemExit("Step 16 queue demo differs from committed report")
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/generate_step16_fixture.py"),
                "--output-root",
                temporary,
                "--executable",
                str(executable),
            ],
            check=True,
            cwd=ROOT,
        )
        regenerated = Path(temporary) / "step16-queue-model-validation/manifest.json"
        regenerated_result = verify_queue_model_report(regenerated)
        for relative in ("manifest.json", "report.json", "scenario-comparison.csv", "sensitivity.csv"):
            if (manifest_path.parent / relative).read_bytes() != (regenerated.parent / relative).read_bytes():
                raise SystemExit(f"Step 16 artifact is not deterministic: {relative}")
        if committed != regenerated_result:
            raise SystemExit("Step 16 verification result changed on regeneration")
    print(json.dumps(committed, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
