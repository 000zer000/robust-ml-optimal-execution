from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from robust_execution.historical_replay import (
    HistoricalReplayError,
    build_historical_replay,
    load_historical_replay_config,
    verify_historical_replay,
)


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "data/sample/canonical/step14-canonical-fixture/dataset-manifest.json"
CONFIG = ROOT / "configs/data/binance_historical_replay_sample.json"


def _config():
    return load_historical_replay_config(CONFIG)


def test_build_and_verify_replay(tmp_path: Path) -> None:
    manifest = build_historical_replay(CANONICAL, _config(), tmp_path)
    result = verify_historical_replay(manifest)
    assert result["events"] == 10
    assert result["observations"] == 8
    assert result["connections"] == 2
    assert result["research_admissible"] is False
    payload = json.loads(manifest.read_text())
    assert payload["exact_fifo_reconstructed"] is False
    assert payload["endogenous_impact_modelled"] is False


def test_build_is_create_only(tmp_path: Path) -> None:
    build_historical_replay(CANONICAL, _config(), tmp_path)
    with pytest.raises(HistoricalReplayError, match="already exists"):
        build_historical_replay(CANONICAL, _config(), tmp_path)


def test_symbol_mismatch_is_rejected(tmp_path: Path) -> None:
    config = _config()
    changed = replace(config, symbols=("ETHUSDT", "BTCUSDT"))
    with pytest.raises(HistoricalReplayError, match="symbols"):
        build_historical_replay(CANONICAL, changed, tmp_path)


def test_research_input_requirement_blocks_sample(tmp_path: Path) -> None:
    config = _config()
    changed = replace(config, require_research_admissible_input=True)
    with pytest.raises(HistoricalReplayError, match="research-admissible"):
        build_historical_replay(CANONICAL, changed, tmp_path)


def test_proxy_permission_is_required_for_sample(tmp_path: Path) -> None:
    config = _config()
    changed = replace(config, allow_connection_start_proxy_for_sample=False)
    with pytest.raises(HistoricalReplayError, match="proxy"):
        build_historical_replay(CANONICAL, changed, tmp_path)


def test_tampered_canonical_input_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "canonical"
    shutil.copytree(CANONICAL.parent, copied)
    manifest = json.loads((copied / "dataset-manifest.json").read_text())
    snapshot = next(item for item in manifest["tables"] if item["table_name"] == "book_snapshots")
    path = copied / snapshot["data_relative_path"]
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(Exception):
        build_historical_replay(copied / "dataset-manifest.json", _config(), tmp_path / "out")


def test_reconnect_clears_stale_book_and_suppresses_prebridge_observation() -> None:
    from robust_execution.historical_replay.builder import _materialize_symbol_events

    def event(
        kind: str,
        connection: str,
        available: int,
        sequence: int,
        payload: object,
        priority: int,
    ) -> dict[str, object]:
        return {
            "symbol": "BTCUSDT",
            "connection_id": connection,
            "event_kind": kind,
            "event_time_ns": available,
            "receive_time_ns": available,
            "available_time_ns": available,
            "canonical_message_sequence": sequence,
            "source_sequence_start": sequence,
            "source_sequence_end": sequence,
            "row_count": 1,
            "payload": payload,
            "snapshot_timestamp_semantics": "test",
            "priority": priority,
        }

    staged = [
        event("connection_reset", "c0", 0, 1, {}, -1),
        event("snapshot", "c0", 10, 2, {"bids": [[100, 10]], "asks": [[102, 10]]}, 0),
        event(
            "depth_batch",
            "c0",
            10,
            2,
            [{"side": "bid", "price_ticks": 100, "quantity_lots": 11, "is_delete": False}],
            1,
        ),
        event(
            "trade",
            "c0",
            20,
            3,
            {"trade_id": 1, "price_ticks": 102, "quantity_lots": 1, "aggressor_side": "buy"},
            2,
        ),
        event("connection_reset", "c1", 30, 4, {}, -1),
        event(
            "trade",
            "c1",
            35,
            5,
            {"trade_id": 2, "price_ticks": 105, "quantity_lots": 1, "aggressor_side": "buy"},
            2,
        ),
        event("snapshot", "c1", 40, 6, {"bids": [[104, 20]], "asks": [[106, 20]]}, 0),
        event(
            "depth_batch",
            "c1",
            40,
            6,
            [{"side": "ask", "price_ticks": 106, "quantity_lots": 21, "is_delete": False}],
            1,
        ),
    ]
    staged.sort(
        key=lambda item: (
            int(item["available_time_ns"]),
            int(item["priority"]),
            int(item["canonical_message_sequence"]),
        )
    )
    events, observations, next_event, next_observation = _materialize_symbol_events(
        staged, _config(), "BTCUSDT", 0, 0
    )
    assert len(events) == 6
    assert len(observations) == 3
    assert next_event == 6
    assert next_observation == 3
    assert observations[-1]["best_bid_ticks"] == 104
    assert observations[-1]["best_ask_ticks"] == 106
    assert observations[-1]["recent_trade_count"] == 1
    assert all(observation["decision_time_ns"] != 35 for observation in observations)
