#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_TO_FIXTURE = {
    "parent-order-v1.schema.json": "parent-order.json",
    "policy-environment-v1.schema.json": "policy-environment.json",
    "policy-action-v1.schema.json": "policy-action.json",
    "policy-observation-v1.schema.json": "policy-observation.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    schemas = ROOT / "schemas" / "policy"
    fixtures = ROOT / "data" / "sample" / "policy"
    actual = {path.name for path in schemas.glob("*.json")}
    if actual != set(SCHEMA_TO_FIXTURE):
        raise RuntimeError(f"policy schema catalog mismatch: {sorted(actual)}")

    for schema_name, fixture_name in sorted(SCHEMA_TO_FIXTURE.items()):
        schema_path = schemas / schema_name
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise RuntimeError(f"wrong JSON Schema dialect: {schema_name}")
        if not str(schema.get("$id", "")).endswith(schema_name):
            raise RuntimeError(f"schema ID mismatch: {schema_name}")
        document = json.loads((fixtures / fixture_name).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(document)

    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    expected_names = set(SCHEMA_TO_FIXTURE.values())
    if set(manifest["artifacts"]) != expected_names:
        raise RuntimeError("policy fixture manifest catalog mismatch")
    for name, expected in manifest["artifacts"].items():
        if sha256(fixtures / name) != expected:
            raise RuntimeError(f"policy fixture manifest mismatch: {name}")

    action = json.loads((fixtures / "policy-action.json").read_text(encoding="utf-8"))
    invalid_action = {**action, "payload": {**action["payload"], "order_type": "unknown"}}
    errors = list(
        Draft202012Validator(
            json.loads((schemas / "policy-action-v1.schema.json").read_text(encoding="utf-8"))
        ).iter_errors(invalid_action)
    )
    if not errors:
        raise RuntimeError("negative policy-action schema control unexpectedly passed")

    print("policy contracts: PASS (4 schemas, 4 fixtures, manifest verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
