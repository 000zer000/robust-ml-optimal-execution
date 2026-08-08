"""Create-only compressed storage with checksums and atomic finalisation."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import BinaryIO

from robust_execution.data_capture.models import (
    ArtifactRecord,
    RawMessageRecord,
    canonical_json_bytes,
)


class StorageError(RuntimeError):
    """Raised when immutable capture storage cannot be created safely."""


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_immutable_gzip_blob(path: Path, data: bytes, *, content_type: str) -> ArtifactRecord:
    if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
        raise StorageError(f"refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    with partial.open("xb") as raw_file:
        with gzip.GzipFile(fileobj=raw_file, mode="wb", mtime=0) as compressed:
            compressed.write(data)
        raw_file.flush()
        os.fsync(raw_file.fileno())
    os.replace(partial, path)
    _fsync_parent(path)
    compressed_data = path.read_bytes()
    return ArtifactRecord(
        relative_path=str(path),
        content_type=content_type,
        compression="gzip",
        uncompressed_bytes=len(data),
        compressed_bytes=len(compressed_data),
        record_count=1,
        sha256=hashlib.sha256(compressed_data).hexdigest(),
    )


def write_immutable_json(path: Path, payload: object) -> None:
    if path.exists() or path.with_suffix(path.suffix + ".partial").exists():
        raise StorageError(f"refusing to overwrite immutable JSON: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    data = canonical_json_bytes(payload) + b"\n"
    with partial.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)
    _fsync_parent(path)


class GzipJsonlSegmentWriter:
    """Append records to one temporary gzip member and atomically seal it."""

    def __init__(
        self,
        final_path: Path,
        *,
        fsync_each_record: bool = False,
        fsync_interval_messages: int = 10_000,
    ) -> None:
        if final_path.exists():
            raise StorageError(f"refusing to overwrite segment: {final_path}")
        self.final_path = final_path
        self.partial_path = final_path.with_suffix(final_path.suffix + ".partial")
        if self.partial_path.exists():
            raise StorageError(f"stale partial segment exists: {self.partial_path}")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        self._raw: BinaryIO = self.partial_path.open("xb")
        self._gzip = gzip.GzipFile(fileobj=self._raw, mode="wb", mtime=0)
        if fsync_interval_messages <= 0:
            raise StorageError("fsync_interval_messages must be positive")
        self._fsync_each_record = fsync_each_record
        self._fsync_interval_messages = fsync_interval_messages
        self.records = 0
        self.uncompressed_bytes = 0
        self._closed = False

    def append(self, record: RawMessageRecord) -> None:
        if self._closed:
            raise StorageError("cannot append to a sealed segment")
        encoded = record.to_bytes() + b"\n"
        self._gzip.write(encoded)
        self.records += 1
        self.uncompressed_bytes += len(encoded)
        if self._fsync_each_record or self.records % self._fsync_interval_messages == 0:
            self.flush()

    def flush(self) -> None:
        if self._closed:
            raise StorageError("cannot flush a sealed segment")
        self._gzip.flush()
        self._raw.flush()
        os.fsync(self._raw.fileno())

    def seal(self) -> ArtifactRecord:
        if self._closed:
            raise StorageError("segment already sealed")
        self._gzip.close()
        self._raw.flush()
        os.fsync(self._raw.fileno())
        self._raw.close()
        os.replace(self.partial_path, self.final_path)
        _fsync_parent(self.final_path)
        self._closed = True
        compressed = self.final_path.read_bytes()
        return ArtifactRecord(
            relative_path=str(self.final_path),
            content_type="application/x-ndjson; profile=binance-raw-message-v1",
            compression="gzip",
            uncompressed_bytes=self.uncompressed_bytes,
            compressed_bytes=len(compressed),
            record_count=self.records,
            sha256=hashlib.sha256(compressed).hexdigest(),
        )

    def abort(self) -> None:
        if self._closed:
            return
        try:
            self._gzip.close()
        finally:
            self._raw.close()
            self.partial_path.unlink(missing_ok=True)
            self._closed = True


def verify_segment(path: Path) -> int:
    """Verify gzip integrity and every embedded raw-payload hash."""
    records = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for line in handle:
            payload = json.loads(line)
            raw = payload["raw_payload_utf8"].encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            if digest != payload["raw_payload_sha256"]:
                raise StorageError(f"raw payload hash mismatch at record {records}")
            records += 1
    return records


def artifact_as_dict(artifact: ArtifactRecord, root: Path) -> dict[str, object]:
    value = asdict(artifact)
    value["relative_path"] = str(Path(artifact.relative_path).relative_to(root))
    return value
