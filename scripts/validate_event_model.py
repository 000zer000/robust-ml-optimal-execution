#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.event_model import validate_event_document, verify_audit_log  # noqa: E402
from robust_execution.event_sample import write_event_model_sample  # noqa: E402

SCHEMAS = {
    "event-envelope-v1.schema.json",
    "audit-record-v1.schema.json",
    "instrument-definition-v1.schema.json",
    "episode-metadata-v1.schema.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    schema_directory = ROOT / "schemas" / "event_model"
    actual = {path.name for path in schema_directory.glob("*.json")}
    if actual != SCHEMAS:
        raise RuntimeError(f"schema catalog mismatch: {sorted(actual)}")
    for path in sorted(schema_directory.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise RuntimeError(f"wrong JSON Schema dialect: {path}")
        if not str(schema.get("$id", "")).endswith(path.name):
            raise RuntimeError(f"schema ID mismatch: {path}")

    committed = ROOT / "data" / "sample" / "event_model"
    for line in (committed / "events.jsonl").read_text(encoding="utf-8").splitlines():
        validate_event_document(json.loads(line))
    verification = verify_audit_log(committed / "audit.jsonl")
    manifest = json.loads((committed / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["artifacts"].items():
        if sha256(committed / name) != expected:
            raise RuntimeError(f"sample manifest mismatch: {name}")

    with tempfile.TemporaryDirectory(prefix="step5-event-model-") as temporary:
        regenerated = Path(temporary) / "event_model"
        write_event_model_sample(regenerated)
        for name in (
            "instrument.json",
            "episode.json",
            "events.jsonl",
            "audit.jsonl",
            "manifest.json",
        ):
            if (regenerated / name).read_bytes() != (committed / name).read_bytes():
                raise RuntimeError(f"non-deterministic sample artifact: {name}")

    print(
        "event model: PASS "
        f"({len(SCHEMAS)} schemas, {verification.records} audit records, "
        f"final hash {verification.final_sha256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
