from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from robust_execution.data_capture.models import RawMessageRecord
from robust_execution.data_capture.storage import (
    GzipJsonlSegmentWriter,
    StorageError,
    verify_segment,
    write_immutable_gzip_blob,
    write_immutable_json,
)


def _record(index: int, raw: str = '{"e":"trade","s":"BTCUSDT"}') -> RawMessageRecord:
    return RawMessageRecord(
        schema_version=1,
        run_id="fixture",
        connection_id="connection-0000",
        message_index=index,
        received_utc_ns=100 + index,
        received_monotonic_ns=200 + index,
        stream="btcusdt@trade",
        symbol="BTCUSDT",
        event_type="trade",
        raw_payload_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        raw_payload_utf8=raw,
    )


def test_segment_preserves_exact_payload_and_is_create_only(tmp_path: Path) -> None:
    path = tmp_path / "segment.jsonl.gz"
    writer = GzipJsonlSegmentWriter(path)
    writer.append(_record(0, '{"price":"1.00", "unicode":"é"}'))
    writer.append(_record(1))
    artifact = writer.seal()
    assert artifact.record_count == 2
    assert verify_segment(path) == 2
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    assert records[0]["raw_payload_utf8"] == '{"price":"1.00", "unicode":"é"}'
    with pytest.raises(StorageError):
        GzipJsonlSegmentWriter(path)
    with pytest.raises(StorageError):
        writer.append(_record(2))


def test_segment_detects_tampered_payload_hash(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl.gz"
    writer = GzipJsonlSegmentWriter(path)
    record = _record(0)
    object.__setattr__(record, "raw_payload_sha256", "0" * 64)
    with pytest.raises(ValueError):
        writer.append(record)
    writer.abort()
    assert not path.exists()


def test_immutable_blob_and_json_refuse_overwrite(tmp_path: Path) -> None:
    blob = tmp_path / "blob.json.gz"
    artifact = write_immutable_gzip_blob(blob, b'{"a":1}', content_type="application/json")
    assert artifact.record_count == 1
    assert gzip.decompress(blob.read_bytes()) == b'{"a":1}'
    with pytest.raises(StorageError):
        write_immutable_gzip_blob(blob, b"other", content_type="application/json")

    manifest = tmp_path / "manifest.json"
    write_immutable_json(manifest, {"a": 1})
    with pytest.raises(StorageError):
        write_immutable_json(manifest, {"a": 2})
