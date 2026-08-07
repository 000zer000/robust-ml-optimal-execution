from __future__ import annotations

import json
from pathlib import Path

from robust_execution.event_model import validate_event_document


SCHEMA_DIRECTORY = Path("schemas/event_model")
SAMPLE_DIRECTORY = Path("data/sample/event_model")


def test_schema_catalog_is_parseable_and_versioned() -> None:
    expected = {
        "audit-record-v1.schema.json",
        "episode-metadata-v1.schema.json",
        "event-envelope-v1.schema.json",
        "instrument-definition-v1.schema.json",
    }
    assert {path.name for path in SCHEMA_DIRECTORY.glob("*.json")} == expected
    for path in SCHEMA_DIRECTORY.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert document["$id"].endswith(path.name)
        assert document["additionalProperties"] is False


def test_committed_event_fixture_validates() -> None:
    lines = (SAMPLE_DIRECTORY / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 9
    for line in lines:
        validate_event_document(json.loads(line))


def test_committed_manifest_matches_artifacts() -> None:
    import hashlib

    manifest = json.loads((SAMPLE_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_claim"] is None
    for name, expected_hash in manifest["artifacts"].items():
        actual = hashlib.sha256((SAMPLE_DIRECTORY / name).read_bytes()).hexdigest()
        assert actual == expected_hash
