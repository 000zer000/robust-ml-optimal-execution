from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_gate_b_report_schema_and_fixture() -> None:
    schema = json.loads(
        (ROOT / "schemas/validation/simulator-validation-report-v1.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    report = json.loads((ROOT / "data/sample/validation/report.json").read_text())
    Draft202012Validator(schema).validate(report)
    assert report["decision"] == "pass"
    assert all(check["passed"] for check in report["checks"])
    assert all(item["passed"] for item in report["sensitivities"])


def test_gate_b_schema_rejects_invalid_decision() -> None:
    schema = json.loads(
        (ROOT / "schemas/validation/simulator-validation-report-v1.schema.json").read_text()
    )
    report = json.loads((ROOT / "data/sample/validation/report.json").read_text())
    report["decision"] = "green"
    assert list(Draft202012Validator(schema).iter_errors(report))
