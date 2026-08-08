"""Canonical columnar table helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.data_capture.storage import write_immutable_gzip_blob, write_immutable_json


@dataclass(frozen=True)
class TableArtifact:
    table_name: str
    row_count: int
    schema_relative_path: str
    data_relative_path: str
    schema_sha256: str
    data_sha256: str
    compressed_bytes: int
    uncompressed_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "table_name": self.table_name,
            "row_count": self.row_count,
            "schema_relative_path": self.schema_relative_path,
            "data_relative_path": self.data_relative_path,
            "schema_sha256": self.schema_sha256,
            "data_sha256": self.data_sha256,
            "compressed_bytes": self.compressed_bytes,
            "uncompressed_bytes": self.uncompressed_bytes,
        }


def rows_to_columns(
    rows: list[dict[str, Any]], column_order: tuple[str, ...]
) -> dict[str, list[Any]]:
    columns: dict[str, list[Any]] = {name: [] for name in column_order}
    for row in rows:
        if set(row) != set(column_order):
            missing = sorted(set(column_order) - set(row))
            extra = sorted(set(row) - set(column_order))
            raise ValueError(f"row columns mismatch: missing={missing}, extra={extra}")
        for name in column_order:
            columns[name].append(row[name])
    return columns


def write_columnar_table(
    dataset_root: Path,
    table_name: str,
    rows: list[dict[str, Any]],
    schema: dict[str, object],
    column_order: tuple[str, ...],
) -> TableArtifact:
    table_root = dataset_root / "tables" / table_name
    schema_path = table_root / "schema.json"
    data_path = table_root / "columns.json.gz"
    payload = {
        "schema_version": 1,
        "physical_format": "re_columnar_v1",
        "table_name": table_name,
        "row_count": len(rows),
        "column_order": list(column_order),
        "columns": rows_to_columns(rows, column_order),
    }
    write_immutable_json(schema_path, schema)
    uncompressed = canonical_json_bytes(payload) + b"\n"
    artifact = write_immutable_gzip_blob(
        data_path,
        uncompressed,
        content_type=f"application/json; profile=re-columnar-v1; table={table_name}",
    )
    return TableArtifact(
        table_name=table_name,
        row_count=len(rows),
        schema_relative_path=str(schema_path.relative_to(dataset_root)),
        data_relative_path=str(data_path.relative_to(dataset_root)),
        schema_sha256=hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        data_sha256=artifact.sha256,
        compressed_bytes=artifact.compressed_bytes,
        uncompressed_bytes=artifact.uncompressed_bytes,
    )
