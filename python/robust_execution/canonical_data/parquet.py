"""Pinned PyArrow export for research-admissible Step 14 datasets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from robust_execution.canonical_data.models import rows_to_columns


class ParquetExportError(RuntimeError):
    """Raised when mandatory research Parquet output cannot be written."""


def _arrow_type(pa: Any, logical_type: str) -> Any:
    if logical_type == "bool":
        return pa.bool_()
    if logical_type in {"int64", "timestamp_ns_utc", "duration_ns"}:
        return pa.int64()
    return pa.string()


def write_parquet_table(
    path: Path,
    rows: list[dict[str, Any]],
    schema: dict[str, object],
    column_order: tuple[str, ...],
) -> dict[str, object]:
    """Write one Parquet table with the repository-pinned PyArrow implementation."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ParquetExportError(
            "pyarrow==25.0.0 is required for research-processed canonical data"
        ) from exc
    if getattr(pa, "__version__", None) != "25.0.0":
        raise ParquetExportError("canonical Parquet export requires exactly pyarrow==25.0.0")
    schema_columns = schema.get("columns")
    if not isinstance(schema_columns, list):
        raise ParquetExportError("canonical schema columns are missing")
    logical = {
        str(item["name"]): str(item["logical_type"])
        for item in schema_columns
        if isinstance(item, dict)
    }
    columns = rows_to_columns(rows, column_order)
    arrays = {
        name: pa.array(columns[name], type=_arrow_type(pa, logical[name]))
        for name in column_order
    }
    table = pa.table(arrays)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ParquetExportError(f"refusing to overwrite Parquet artifact: {path}")
    pq.write_table(
        table,
        path,
        compression="zstd",
        version="2.6",
        write_statistics=True,
        use_dictionary=True,
    )
    return {
        "relative_path": "",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "rows": table.num_rows,
        "pyarrow_version": pa.__version__,
    }
