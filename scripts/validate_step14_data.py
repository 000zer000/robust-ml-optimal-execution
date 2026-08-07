#!/usr/bin/env python3
"""Validate Step 14 schemas, configuration, and committed canonical fixture."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import tempfile

import jsonschema

from robust_execution.canonical_data import (
    build_canonical_dataset,
    load_canonical_data_config,
    verify_canonical_dataset,
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    schema_root = root / "schemas/data"
    config_path = root / "configs/data/binance_canonical_sample.json"
    manifest_path = root / "data/sample/canonical/step14-canonical-fixture/dataset-manifest.json"
    config_schema = json.loads((schema_root / "canonical-data-config-v1.schema.json").read_text())
    manifest_schema = json.loads((schema_root / "canonical-dataset-manifest-v1.schema.json").read_text())
    table_schema = json.loads((schema_root / "canonical-columnar-table-v1.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(config_schema)
    jsonschema.Draft202012Validator.check_schema(manifest_schema)
    jsonschema.Draft202012Validator.check_schema(table_schema)
    jsonschema.validate(json.loads(config_path.read_text()), config_schema)
    manifest = json.loads(manifest_path.read_text())
    jsonschema.validate(manifest, manifest_schema)
    for item in manifest["tables"]:
        with gzip.open(manifest_path.parent / item["data_relative_path"], "rt") as handle:
            jsonschema.validate(json.load(handle), table_schema)
    result = verify_canonical_dataset(manifest_path)
    with tempfile.TemporaryDirectory() as temporary:
        output_root = Path(temporary)
        regenerated = build_canonical_dataset(
            root / "data/sample/validation_step13/step13-full-day-fixture/manifest.json",
            root / "results/validation/step13/step13-fixture-validation/validation-report.json",
            load_canonical_data_config(config_path),
            output_root,
            dataset_id="step14-canonical-fixture",
        )
        committed_root = manifest_path.parent
        regenerated_root = regenerated.parent
        committed = {
            str(path.relative_to(committed_root)): path.read_bytes()
            for path in committed_root.rglob("*")
            if path.is_file()
        }
        recreated = {
            str(path.relative_to(regenerated_root)): path.read_bytes()
            for path in regenerated_root.rglob("*")
            if path.is_file()
        }
        if committed != recreated:
            raise SystemExit("Step 14 deterministic regeneration differs")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
