from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from robust_execution.prediction import (
    BookUpdate,
    DecisionPoint,
    PredictionDataError,
    build_feature_label_rows,
    load_prediction_feature_config,
)
from robust_execution.prediction.fixture import NS, validation_fixture
from robust_execution.prediction.models import PredictionMarketEvent

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/models/step21_causal_features_sample.json"


def _config():
    return load_prediction_feature_config(CONFIG)


def _row(rows, symbol: str, side: str, decision_time_ns: int):
    return next(
        row
        for row in rows
        if row.feature["symbol"] == symbol
        and row.feature["passive_side"] == side
        and row.feature["decision_time_ns"] == decision_time_ns
    )


def test_prediction_labels_and_timestamp_contract() -> None:
    events, decisions, coverage = validation_fixture()
    rows = build_feature_label_rows(events, decisions, coverage, _config())
    assert len(rows) == 8
    first_ask = _row(rows, "BTCUSDT", "ask", 6 * NS)
    first_bid = _row(rows, "BTCUSDT", "bid", 6 * NS)
    second_ask = _row(rows, "BTCUSDT", "ask", 9 * NS)
    second_bid = _row(rows, "BTCUSDT", "bid", 9 * NS)
    eth_second_ask = _row(rows, "ETHUSDT", "ask", 9 * NS)
    eth_second_bid = _row(rows, "ETHUSDT", "bid", 9 * NS)
    assert [first_ask.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [1, 1, 1]
    assert [first_bid.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [0, 0, 1]
    assert [second_ask.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [0, 0, 1]
    assert [second_bid.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [1, 1, 1]
    assert [eth_second_ask.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [
        0,
        0,
        0,
    ]
    assert [eth_second_bid.label[f"quote_depletion_{h}"] for h in ("250ms", "1s", "5s")] == [
        0,
        0,
        0,
    ]
    for row in rows:
        assert row.feature["maximum_source_event_time_ns"] <= row.feature["source_cutoff_ns"]
        assert row.feature["maximum_source_available_time_ns"] <= row.feature["decision_time_ns"]
        assert row.label["target_start_exclusive_ns"] == row.feature["source_cutoff_ns"]


def test_future_label_mutation_cannot_change_same_decision_features() -> None:
    events, decisions, coverage = validation_fixture()
    baseline = build_feature_label_rows(events, decisions, coverage, _config())
    target = next(
        e
        for e in events
        if e.symbol == "BTCUSDT" and e.kind == "depth" and e.event_time_ns == 6_050_000_000
    )
    mutated = [
        replace(e, updates=(BookUpdate("ask", 101, 70),)) if e.sequence == target.sequence else e
        for e in events
    ]
    changed = build_feature_label_rows(mutated, decisions, coverage, _config())
    before = _row(baseline, "BTCUSDT", "ask", 6 * NS)
    after = _row(changed, "BTCUSDT", "ask", 6 * NS)
    assert before.feature == after.feature
    assert before.label["quote_depletion_250ms"] == 1
    assert after.label["quote_depletion_250ms"] == 0


def test_mutation_after_all_horizons_changes_nothing() -> None:
    events, decisions, coverage = validation_fixture()
    baseline = build_feature_label_rows(events, decisions, coverage, _config())
    sentinel = next(
        e for e in events if e.symbol == "BTCUSDT" and e.event_time_ns == 14_100_000_000
    )
    mutated = [
        replace(e, trade_quantity_lots=9999) if e.sequence == sentinel.sequence else e
        for e in events
    ]
    changed = build_feature_label_rows(mutated, decisions, coverage, _config())
    assert baseline == changed


def test_past_mutation_changes_feature_but_not_other_symbol() -> None:
    events, decisions, coverage = validation_fixture()
    baseline = build_feature_label_rows(events, decisions, coverage, _config())
    past_trade = next(
        e for e in events if e.symbol == "BTCUSDT" and e.event_time_ns == 5_800_000_000
    )
    mutated = [
        replace(e, trade_quantity_lots=115) if e.sequence == past_trade.sequence else e
        for e in events
    ]
    changed = build_feature_label_rows(mutated, decisions, coverage, _config())
    before = _row(baseline, "BTCUSDT", "bid", 6 * NS)
    after = _row(changed, "BTCUSDT", "bid", 6 * NS)
    assert (
        before.feature["toward_quote_trade_flow_250ms_lots"]
        != after.feature["toward_quote_trade_flow_250ms_lots"]
    )
    eth_before = _row(baseline, "ETHUSDT", "bid", 6 * NS)
    eth_after = _row(changed, "ETHUSDT", "bid", 6 * NS)
    assert eth_before == eth_after


def test_reject_incomplete_history_and_label_coverage() -> None:
    events, _, coverage = validation_fixture()
    with pytest.raises(PredictionDataError, match="feature history"):
        build_feature_label_rows(
            events, [DecisionPoint("BTCUSDT", 5 * NS, "bid")], coverage, _config()
        )
    with pytest.raises(PredictionDataError, match="future label coverage"):
        build_feature_label_rows(
            events,
            [DecisionPoint("BTCUSDT", 9 * NS, "bid")],
            {**coverage, "BTCUSDT": 13 * NS},
            _config(),
        )


def test_reject_snapshot_inside_label_horizon() -> None:
    events, _, coverage = validation_fixture()
    sequence = max(e.sequence for e in events) + 1
    reset = PredictionMarketEvent(
        sequence,
        "BTCUSDT",
        "snapshot",
        10 * NS,
        10 * NS + 100_000_000,
        bids=((100, 10),),
        asks=((101, 10),),
    )
    with pytest.raises(PredictionDataError, match="snapshot/reconnect"):
        build_feature_label_rows(
            sorted([*events, reset], key=lambda e: (e.event_time_ns, e.sequence)),
            [DecisionPoint("BTCUSDT", 6 * NS, "bid")],
            coverage,
            _config(),
        )


def test_reject_bad_stream_order_duplicate_and_availability_inversion() -> None:
    events, decisions, coverage = validation_fixture()
    with pytest.raises(PredictionDataError, match="globally unique"):
        build_feature_label_rows([*events, events[0]], decisions, coverage, _config())
    first_btc = next(e for e in events if e.symbol == "BTCUSDT" and e.kind == "snapshot")
    inverted = [
        replace(e, available_time_ns=1_000_000_000) if e.sequence == first_btc.sequence else e
        for e in events
    ]
    with pytest.raises(PredictionDataError, match="availability"):
        build_feature_label_rows(inverted, decisions, coverage, _config())
    late = next(e for e in events if e.symbol == "BTCUSDT" and e.event_time_ns == 6_050_000_000)
    disordered = [
        replace(e, event_time_ns=100_000_000) if e.sequence == late.sequence else e for e in events
    ]
    with pytest.raises(PredictionDataError, match="strictly ordered"):
        build_feature_label_rows(disordered, decisions, coverage, _config())


def test_reject_bad_decisions_empty_inputs_and_crossed_book() -> None:
    events, decisions, coverage = validation_fixture()
    config = _config()
    with pytest.raises(PredictionDataError, match="cannot be empty"):
        build_feature_label_rows([], decisions, coverage, config)
    with pytest.raises(PredictionDataError, match="one decision"):
        build_feature_label_rows(events, [], coverage, config)
    with pytest.raises(PredictionDataError, match="symbol/side"):
        build_feature_label_rows(
            events, [DecisionPoint("DOGEUSDT", 6 * NS, "bid")], coverage, config
        )
    with pytest.raises(PredictionDataError, match="observation latency"):
        build_feature_label_rows(events, [DecisionPoint("BTCUSDT", 1, "bid")], coverage, config)
    with pytest.raises(PredictionDataError, match="missing label coverage"):
        build_feature_label_rows(
            events,
            [DecisionPoint("BTCUSDT", 6 * NS, "bid")],
            {"ETHUSDT": 15 * NS},
            config,
        )
    with pytest.raises(PredictionDataError, match="duplicate prediction row_id"):
        build_feature_label_rows(
            events, [DecisionPoint("BTCUSDT", 6 * NS, "bid")] * 2, coverage, config
        )
    crossed = list(events)
    first_depth = next(e for e in crossed if e.symbol == "BTCUSDT" and e.kind == "depth")
    crossed[crossed.index(first_depth)] = replace(
        first_depth, updates=(BookUpdate("bid", 102, 10),)
    )
    with pytest.raises(PredictionDataError, match="crossed"):
        build_feature_label_rows(
            crossed, [DecisionPoint("BTCUSDT", 6 * NS, "bid")], coverage, config
        )


@pytest.mark.parametrize(
    "event",
    [
        PredictionMarketEvent(
            -1, "BTCUSDT", "trade", 1, 2, trade_price_ticks=1, trade_quantity_lots=1
        ),
        PredictionMarketEvent(
            1, "btcusdt", "trade", 1, 2, trade_price_ticks=1, trade_quantity_lots=1
        ),
        PredictionMarketEvent(
            1, "BTCUSDT", "trade", 2, 1, trade_price_ticks=1, trade_quantity_lots=1
        ),
        PredictionMarketEvent(1, "BTCUSDT", "snapshot", 1, 2, bids=(), asks=((2, 1),)),
        PredictionMarketEvent(1, "BTCUSDT", "snapshot", 1, 2, bids=((1, 0),), asks=((2, 1),)),
        PredictionMarketEvent(1, "BTCUSDT", "depth", 1, 2, updates=()),
        PredictionMarketEvent(1, "BTCUSDT", "depth", 1, 2, updates=(BookUpdate("bid", 0, 1),)),
        PredictionMarketEvent(
            1, "BTCUSDT", "trade", 1, 2, trade_price_ticks=0, trade_quantity_lots=1
        ),
        PredictionMarketEvent(
            1,
            "BTCUSDT",
            "trade",
            1,
            2,
            bids=((1, 1),),
            trade_price_ticks=1,
            trade_quantity_lots=1,
        ),
    ],
)
def test_event_validation_rejects_malformed_events(event: PredictionMarketEvent) -> None:
    with pytest.raises(PredictionDataError):
        event.validate()
