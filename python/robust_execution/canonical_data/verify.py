"""Independent verification of Step 14 canonical datasets."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


class CanonicalDataVerificationError(RuntimeError):
    """Raised when a canonical dataset is incomplete or internally inconsistent."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalDataVerificationError(f"cannot read {path}: {exc}") from exc


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_canonical_dataset(manifest_path: Path) -> dict[str, object]:
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("step") != 14:
        raise CanonicalDataVerificationError("unsupported Step 14 manifest")
    if manifest.get("research_specification_changed") is not False:
        raise CanonicalDataVerificationError("manifest claims the research specification changed")
    if manifest.get("missing_events_repaired") is not False:
        raise CanonicalDataVerificationError("canonical dataset claims repaired events")
    expected_digest = _read_json(manifest_path.with_name("dataset-manifest.sha256.json"))
    actual_digest = _digest(manifest_path)
    if expected_digest != {"sha256": actual_digest}:
        raise CanonicalDataVerificationError("dataset manifest digest mismatch")
    root = manifest_path.parent
    tables = manifest.get("tables")
    if not isinstance(tables, list) or len(tables) != 6:
        raise CanonicalDataVerificationError("exactly six canonical tables are required")
    table_rows: dict[str, int] = {}
    for item in tables:
        if not isinstance(item, dict):
            raise CanonicalDataVerificationError("table artifact must be an object")
        name = item.get("table_name")
        if not isinstance(name, str) or name in table_rows:
            raise CanonicalDataVerificationError("table names must be unique strings")
        schema_path = root / str(item.get("schema_relative_path"))
        data_path = root / str(item.get("data_relative_path"))
        if _digest(schema_path) != item.get("schema_sha256") or _digest(data_path) != item.get("data_sha256"):
            raise CanonicalDataVerificationError(f"artifact digest mismatch for {name}")
        schema = _read_json(schema_path)
        try:
            with gzip.open(data_path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise CanonicalDataVerificationError(f"cannot read table {name}: {exc}") from exc
        if not isinstance(schema, dict) or schema.get("table_name") != name:
            raise CanonicalDataVerificationError(f"schema table mismatch for {name}")
        if not isinstance(data, dict) or data.get("table_name") != name:
            raise CanonicalDataVerificationError(f"data table mismatch for {name}")
        columns = data.get("columns")
        order = data.get("column_order")
        row_count = data.get("row_count")
        if not isinstance(columns, dict) or not isinstance(order, list) or not isinstance(row_count, int):
            raise CanonicalDataVerificationError(f"malformed columnar table {name}")
        if set(columns) != set(order) or len(order) != len(set(order)):
            raise CanonicalDataVerificationError(f"column order mismatch for {name}")
        if any(not isinstance(values, list) or len(values) != row_count for values in columns.values()):
            raise CanonicalDataVerificationError(f"column lengths differ for {name}")
        if row_count != item.get("row_count"):
            raise CanonicalDataVerificationError(f"row count mismatch for {name}")
        schema_columns = [entry.get("name") for entry in schema.get("columns", []) if isinstance(entry, dict)]
        if schema_columns != order:
            raise CanonicalDataVerificationError(f"schema columns differ for {name}")
        table_rows[name] = row_count
    if table_rows.get("instrument_definitions") != len(manifest.get("symbols", [])):
        raise CanonicalDataVerificationError("instrument table does not cover every symbol")
    if table_rows.get("source_records") != manifest.get("unique_messages"):
        raise CanonicalDataVerificationError("source-record count is inconsistent")
    if table_rows.get("duplicate_records") != manifest.get("exact_duplicates_dropped"):
        raise CanonicalDataVerificationError("duplicate-record count is inconsistent")
    if manifest.get("dataset_classification") == "sample_only_non_research":
        if manifest.get("research_admissible") is not False:
            raise CanonicalDataVerificationError("sample fixture may not be research admissible")
    elif manifest.get("dataset_classification") == "research_processed":
        if manifest.get("research_admissible") is not True:
            raise CanonicalDataVerificationError("processed dataset must be research admissible")
        parquet = manifest.get("parquet")
        if not isinstance(parquet, dict) or parquet.get("required") is not True:
            raise CanonicalDataVerificationError("processed dataset must require Parquet")
    else:
        raise CanonicalDataVerificationError("unknown dataset classification")
    return {
        "status": "ok",
        "dataset_id": manifest.get("dataset_id"),
        "classification": manifest.get("dataset_classification"),
        "tables": len(table_rows),
        "rows": sum(table_rows.values()),
        "manifest_sha256": actual_digest,
        "table_rows": table_rows,
    }
