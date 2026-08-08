"""Read deterministic Step 14 columnar tables."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any


class HistoricalTableError(RuntimeError):
    pass


def read_table(dataset_root: Path, relative_path: str) -> list[dict[str, Any]]:
    path = dataset_root / relative_path
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalTableError(f"cannot read canonical table {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HistoricalTableError("canonical table payload must be an object")
    columns = payload.get("columns")
    order = payload.get("column_order")
    row_count = payload.get("row_count")
    if (
        not isinstance(columns, dict)
        or not isinstance(order, list)
        or not isinstance(row_count, int)
    ):
        raise HistoricalTableError("canonical table payload is malformed")
    if set(columns) != set(order):
        raise HistoricalTableError("canonical table columns do not match column_order")
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        row: dict[str, Any] = {}
        for name in order:
            values = columns.get(name)
            if not isinstance(values, list) or len(values) != row_count:
                raise HistoricalTableError("canonical table column length mismatch")
            row[str(name)] = values[index]
        rows.append(row)
    return rows
