from __future__ import annotations

from decimal import Decimal

import pytest

from robust_execution.data_capture.sequence import (
    DepthSynchronizer,
    SequenceError,
    SyncState,
    parse_depth_update,
)


def update(first: int, final: int, *, bid: str = "100", ask: str = "101") -> object:
    return parse_depth_update(
        {
            "e": "depthUpdate",
            "E": 1_000_000,
            "s": "BTCUSDT",
            "U": first,
            "u": final,
            "b": [[bid, "2"]],
            "a": [[ask, "3"]],
        }
    )


def snapshot(last: int = 100) -> dict[str, object]:
    return {
        "lastUpdateId": last,
        "bids": [["99", "5"], ["98", "4"]],
        "asks": [["102", "5"], ["103", "4"]],
    }


def test_buffer_snapshot_and_apply_contiguous_updates() -> None:
    sync = DepthSynchronizer("BTCUSDT")
    assert sync.ingest(update(100, 101)) == "buffered"
    assert sync.install_snapshot(snapshot())
    assert sync.state is SyncState.SYNCHRONIZED
    assert sync.local_update_id == 101
    assert sync.book.best_bid() == Decimal("100")
    assert sync.book.best_ask() == Decimal("101")
    assert sync.ingest(update(102, 102, bid="100.5", ask="101.5")) == "applied"
    assert sync.local_update_id == 102


def test_stale_non_overlapping_snapshot_requires_refetch() -> None:
    sync = DepthSynchronizer("BTCUSDT")
    sync.ingest(update(110, 111))
    assert not sync.install_snapshot(snapshot(100))
    assert sync.state is SyncState.BUFFERING


def test_duplicate_old_and_gap_are_distinguished() -> None:
    sync = DepthSynchronizer("BTCUSDT")
    assert sync.install_snapshot(snapshot())
    assert sync.ingest(update(100, 100)) == "duplicate"
    assert sync.ingest(update(99, 99)) == "ignored_old"
    assert sync.ingest(update(103, 103)) == "gap"
    assert sync.state is SyncState.INVALID
    assert sync.diagnostics.gaps == 1
    assert sync.diagnostics.resynchronizations == 1


def test_crossed_update_invalidates_without_mutating_valid_book() -> None:
    sync = DepthSynchronizer("BTCUSDT")
    assert sync.install_snapshot(snapshot())
    prior_bid = sync.book.best_bid()
    prior_ask = sync.book.best_ask()
    with pytest.raises(SequenceError, match="crossed"):
        sync.ingest(update(101, 101, bid="104", ask="101"))
    assert sync.state is SyncState.INVALID
    assert prior_bid == Decimal("99")
    assert prior_ask == Decimal("102")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"e": "trade"},
        {"e": "depthUpdate", "s": "BTCUSDT", "U": 2, "u": 1, "E": 1, "b": [], "a": []},
        {"e": "depthUpdate", "s": "BTCUSDT", "U": 1, "u": 2, "E": 1, "b": [["1"]], "a": []},
    ],
)
def test_malformed_depth_update_is_rejected(payload: object) -> None:
    with pytest.raises(SequenceError):
        parse_depth_update(payload)
