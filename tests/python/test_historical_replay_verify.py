from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from robust_execution.historical_replay.verify import (
    HistoricalReplayVerificationError,
    verify_historical_replay,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/sample/historical_replay/step15-historical-fixture"


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "replay"
    shutil.copytree(SOURCE, target)
    return target / "replay-manifest.json"


def _rewrite_manifest(path: Path, mutate) -> None:
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
    path.with_name("replay-manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True) + "\n"
    )


def test_committed_replay_verifies() -> None:
    result = verify_historical_replay(SOURCE / "replay-manifest.json")
    assert result["status"] == "ok"


@pytest.mark.parametrize(
    "field,value",
    [
        ("research_specification_changed", True),
        ("exact_fifo_reconstructed", True),
        ("endogenous_impact_modelled", True),
        ("queue_position_semantics", "exact_fifo"),
    ],
)
def test_weakened_claim_boundaries_are_rejected(tmp_path: Path, field: str, value: object) -> None:
    manifest = _copy(tmp_path)
    _rewrite_manifest(manifest, lambda data: data.__setitem__(field, value))
    with pytest.raises(HistoricalReplayVerificationError):
        verify_historical_replay(manifest)


def test_manifest_digest_tamper_is_rejected(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    data = json.loads(manifest.read_text())
    data["event_count"] += 1
    manifest.write_text(json.dumps(data))
    with pytest.raises(HistoricalReplayVerificationError, match="digest"):
        verify_historical_replay(manifest)


def test_table_digest_tamper_is_rejected(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    data = json.loads(manifest.read_text())
    path = manifest.parent / data["tables"][0]["data_relative_path"]
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(HistoricalReplayVerificationError, match="table digest"):
        verify_historical_replay(manifest)


def test_causal_observation_tamper_is_rejected(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    data = json.loads(manifest.read_text())
    table = next(item for item in data["tables"] if item["table_name"] == "replay_observations")
    path = manifest.parent / table["data_relative_path"]
    with gzip.open(path, "rt") as handle:
        payload = json.load(handle)
    payload["columns"]["decision_time_ns"][0] = 0
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as handle:
        handle.write((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode())
    table["data_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.with_name("replay-manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}, sort_keys=True)
        + "\n"
    )
    with pytest.raises(HistoricalReplayVerificationError, match="unavailable"):
        verify_historical_replay(manifest)


def test_unsupported_manifest_and_table_set_are_rejected(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    _rewrite_manifest(manifest, lambda data: data.__setitem__("step", 14))
    with pytest.raises(HistoricalReplayVerificationError, match="unsupported"):
        verify_historical_replay(manifest)

    manifest = _copy(tmp_path / "second")
    _rewrite_manifest(manifest, lambda data: data["tables"].pop())
    with pytest.raises(HistoricalReplayVerificationError, match="three"):
        verify_historical_replay(manifest)


def test_count_and_crossed_book_tampering_are_rejected(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    _rewrite_manifest(manifest, lambda data: data.__setitem__("event_count", 999))
    with pytest.raises(HistoricalReplayVerificationError, match="counts"):
        verify_historical_replay(manifest)

    manifest = _copy(tmp_path / "crossed")
    data = json.loads(manifest.read_text())
    table = next(item for item in data["tables"] if item["table_name"] == "replay_observations")
    path = manifest.parent / table["data_relative_path"]
    with gzip.open(path, "rt") as handle:
        payload = json.load(handle)
    payload["columns"]["best_bid_ticks"][0] = payload["columns"]["best_ask_ticks"][0]
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as handle:
        handle.write((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode())
    table["data_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.with_name("replay-manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}, sort_keys=True)
        + "\n"
    )
    with pytest.raises(HistoricalReplayVerificationError, match="crossed"):
        verify_historical_replay(manifest)
