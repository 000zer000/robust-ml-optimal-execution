from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from robust_execution.historical_replay.tables import HistoricalTableError, read_table


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as handle:
        handle.write(json.dumps(value).encode())


def test_read_valid_table(tmp_path: Path) -> None:
    _write(
        tmp_path / "table.gz",
        {"columns": {"a": [1], "b": [2]}, "column_order": ["a", "b"], "row_count": 1},
    )
    assert read_table(tmp_path, "table.gz") == [{"a": 1, "b": 2}]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"columns": {"a": [1]}, "column_order": ["b"], "row_count": 1},
        {"columns": {"a": []}, "column_order": ["a"], "row_count": 1},
    ],
)
def test_reject_malformed_table(tmp_path: Path, payload: object) -> None:
    _write(tmp_path / "table.gz", payload)
    with pytest.raises(HistoricalTableError):
        read_table(tmp_path, "table.gz")


def test_reject_missing_and_invalid_gzip(tmp_path: Path) -> None:
    with pytest.raises(HistoricalTableError, match="cannot read"):
        read_table(tmp_path, "missing.gz")
    (tmp_path / "bad.gz").write_bytes(b"not gzip")
    with pytest.raises(HistoricalTableError, match="cannot read"):
        read_table(tmp_path, "bad.gz")
