"""Leakage-safe Step 21 feature and target construction."""

from __future__ import annotations

import hashlib
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass

from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.prediction.config import PredictionFeatureConfig
from robust_execution.prediction.models import (
    DecisionPoint,
    FeatureLabelRow,
    PredictionDataError,
    PredictionMarketEvent,
    Side,
)


@dataclass(frozen=True)
class _BookSummary:
    time_ns: int
    best_bid: int
    best_ask: int
    bid_top1: int
    ask_top1: int
    bid_topn: int
    ask_topn: int
    mid2: int
    spread: int
    bid_best_since_ns: int
    ask_best_since_ns: int


@dataclass(frozen=True)
class _Trade:
    time_ns: int
    quantity_lots: int
    buyer_is_maker: bool


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _trunc_ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise PredictionDataError("ratio denominator must be positive")
    sign = -1 if numerator < 0 else 1
    return sign * (abs(numerator) // denominator)


def _top(book: dict[int, int], n: int, reverse: bool) -> list[tuple[int, int]]:
    return sorted(book.items(), reverse=reverse)[:n]


def _validate_book(bids: dict[int, int], asks: dict[int, int]) -> None:
    if not bids or not asks or max(bids) >= min(asks):
        raise PredictionDataError("prediction book is empty, locked, or crossed")


def _summary(
    bids: dict[int, int],
    asks: dict[int, int],
    top_levels: int,
    time_ns: int,
    previous: _BookSummary | None,
) -> _BookSummary:
    _validate_book(bids, asks)
    bid_levels = _top(bids, top_levels, True)
    ask_levels = _top(asks, top_levels, False)
    best_bid = bid_levels[0][0]
    best_ask = ask_levels[0][0]
    bid_since = time_ns
    ask_since = time_ns
    if previous is not None:
        if previous.best_bid == best_bid:
            bid_since = previous.bid_best_since_ns
        if previous.best_ask == best_ask:
            ask_since = previous.ask_best_since_ns
    return _BookSummary(
        time_ns=time_ns,
        best_bid=best_bid,
        best_ask=best_ask,
        bid_top1=bid_levels[0][1],
        ask_top1=ask_levels[0][1],
        bid_topn=sum(quantity for _, quantity in bid_levels),
        ask_topn=sum(quantity for _, quantity in ask_levels),
        mid2=best_bid + best_ask,
        spread=best_ask - best_bid,
        bid_best_since_ns=bid_since,
        ask_best_since_ns=ask_since,
    )


def _apply_event(
    event: PredictionMarketEvent,
    bids: dict[int, int],
    asks: dict[int, int],
) -> None:
    if event.kind == "snapshot":
        bids.clear()
        asks.clear()
        bids.update(dict(event.bids))
        asks.update(dict(event.asks))
    elif event.kind == "depth":
        for update in event.updates:
            book = bids if update.side == "bid" else asks
            if update.quantity_lots == 0:
                book.pop(update.price_ticks, None)
            else:
                book[update.price_ticks] = update.quantity_lots
    if event.kind != "trade":
        _validate_book(bids, asks)


def _past_summary(history: list[_BookSummary], cutoff_ns: int) -> _BookSummary:
    times = [item.time_ns for item in history]
    index = bisect_right(times, cutoff_ns) - 1
    if index < 0:
        return history[0]
    return history[index]


def _window_trades(
    trades: list[_Trade], start_exclusive: int, cutoff_inclusive: int
) -> list[_Trade]:
    return [item for item in trades if start_exclusive < item.time_ns <= cutoff_inclusive]


def _toward_quote_flow(trades: Iterable[_Trade], side: Side) -> int:
    total = 0
    for trade in trades:
        seller_aggressor = trade.buyer_is_maker
        toward = seller_aggressor if side == "bid" else not seller_aggressor
        total += trade.quantity_lots if toward else -trade.quantity_lots
    return total


def _side_values(summary: _BookSummary, side: Side) -> tuple[int, int, int, int, int]:
    if side == "bid":
        return (
            summary.bid_top1,
            summary.ask_top1,
            summary.bid_topn,
            summary.ask_topn,
            summary.bid_best_since_ns,
        )
    return (
        summary.ask_top1,
        summary.bid_top1,
        summary.ask_topn,
        summary.bid_topn,
        summary.ask_best_since_ns,
    )


def _feature_row(
    config: PredictionFeatureConfig,
    point: DecisionPoint,
    eligible: list[PredictionMarketEvent],
) -> dict[str, object]:
    cutoff = point.decision_time_ns - config.observation_latency_ns
    bids: dict[int, int] = {}
    asks: dict[int, int] = {}
    history: list[_BookSummary] = []
    trades: list[_Trade] = []
    source_sequences: list[int] = []
    maximum_available = 0
    current: _BookSummary | None = None
    for event in eligible:
        if event.symbol != point.symbol:
            continue
        if event.event_time_ns > cutoff or event.available_time_ns > point.decision_time_ns:
            continue
        if event.kind == "snapshot":
            current = None
            history.clear()
            trades.clear()
            source_sequences.clear()
            maximum_available = 0
        _apply_event(event, bids, asks)
        source_sequences.append(event.sequence)
        maximum_available = max(maximum_available, event.available_time_ns)
        if event.kind == "trade":
            trades.append(
                _Trade(event.event_time_ns, event.trade_quantity_lots, event.buyer_is_maker)
            )
        else:
            current = _summary(bids, asks, config.top_levels, event.event_time_ns, current)
            history.append(current)
    if current is None or not source_sequences:
        raise PredictionDataError("decision point has no synchronized causal book state")
    if history[0].time_ns > cutoff - config.maximum_feature_window_ns:
        raise PredictionDataError("decision point lacks complete causal feature history")
    same1, opp1, same_n, opp_n, quote_since = _side_values(current, point.passive_side)
    side_sign = 1 if point.passive_side == "bid" else -1
    features: dict[str, int] = {
        "spread_ticks": current.spread,
        "same_top1_lots": same1,
        "opposite_top1_lots": opp1,
        "same_top5_lots": same_n,
        "opposite_top5_lots": opp_n,
        "side_imbalance_top1_bps": _trunc_ratio(10_000 * (same1 - opp1), same1 + opp1),
        "side_imbalance_top5_bps": _trunc_ratio(10_000 * (same_n - opp_n), same_n + opp_n),
    }
    for window, suffix in (
        (250_000_000, "250ms"),
        (1_000_000_000, "1s"),
        (5_000_000_000, "5s"),
    ):
        start = cutoff - window
        window_trades = _window_trades(trades, start, cutoff)
        features[f"toward_quote_trade_flow_{suffix}_lots"] = _toward_quote_flow(
            window_trades, point.passive_side
        )
        past = _past_summary(history, start)
        features[f"side_mid_move_{suffix}_half_ticks"] = side_sign * (current.mid2 - past.mid2)
    one_second_trades = _window_trades(trades, cutoff - 1_000_000_000, cutoff)
    five_second_trades = _window_trades(trades, cutoff - 5_000_000_000, cutoff)
    features["trade_count_1s"] = len(one_second_trades)
    features["trade_count_5s"] = len(five_second_trades)
    for window, suffix in ((1_000_000_000, "1s"), (5_000_000_000, "5s")):
        start = cutoff - window
        past = _past_summary(history, start)
        relevant = [item for item in history if start < item.time_ns <= cutoff]
        previous_mid2 = past.mid2
        realized = 0
        for item in relevant:
            realized += abs(item.mid2 - previous_mid2)
            previous_mid2 = item.mid2
        features[f"realized_abs_mid_move_{suffix}_half_ticks"] = realized
        features[f"spread_change_{suffix}_ticks"] = current.spread - past.spread
    features["quote_age_ns"] = max(0, cutoff - quote_since)
    last_trade = max((trade.time_ns for trade in trades if trade.time_ns <= cutoff), default=None)
    features["time_since_last_trade_ns"] = (
        config.maximum_feature_window_ns + 1 if last_trade is None else max(0, cutoff - last_trade)
    )
    lineage = {
        "symbol": point.symbol,
        "decision_time_ns": point.decision_time_ns,
        "source_cutoff_ns": cutoff,
        "source_sequences": source_sequences,
    }
    row_id = _sha256({"lineage": lineage, "passive_side": point.passive_side})[:24]
    return {
        "row_id": row_id,
        "symbol": point.symbol,
        "passive_side": point.passive_side,
        "decision_time_ns": point.decision_time_ns,
        "source_cutoff_ns": cutoff,
        "maximum_source_event_time_ns": max(
            event.event_time_ns
            for event in eligible
            if event.symbol == point.symbol
            and event.event_time_ns <= cutoff
            and event.available_time_ns <= point.decision_time_ns
        ),
        "maximum_source_available_time_ns": maximum_available,
        "first_source_sequence": min(source_sequences),
        "last_source_sequence": max(source_sequences),
        "source_event_count": len(source_sequences),
        "lineage_sha256": _sha256(lineage),
        "best_bid_ticks": current.best_bid,
        "best_ask_ticks": current.best_ask,
        "mid_price_x2": current.mid2,
        **features,
    }


def _future_label(
    config: PredictionFeatureConfig,
    point: DecisionPoint,
    feature: dict[str, object],
    events: list[PredictionMarketEvent],
    coverage_end_ns: int,
) -> dict[str, object]:
    def feature_int(name: str) -> int:
        value = feature.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise PredictionDataError(f"feature {name} must be an integer")
        return value

    cutoff = feature_int("source_cutoff_ns")
    if coverage_end_ns < cutoff + config.maximum_horizon_ns:
        raise PredictionDataError("decision point lacks complete future label coverage")
    bids: dict[int, int] = {}
    asks: dict[int, int] = {}
    current_mid2 = feature_int("mid_price_x2")
    quote_field = "best_bid_ticks" if point.passive_side == "bid" else "best_ask_ticks"
    initial_quote = feature_int(quote_field)
    # Reconstruct the book exactly at the feature cutoff without using availability.
    for event in events:
        if event.symbol != point.symbol or event.event_time_ns > cutoff:
            continue
        _apply_event(event, bids, asks)
    _validate_book(bids, asks)
    future = [
        event
        for event in events
        if event.symbol == point.symbol
        and cutoff < event.event_time_ns <= cutoff + config.maximum_horizon_ns
    ]
    future.sort(key=lambda item: (item.event_time_ns, item.sequence))
    depletion_time: int | None = None
    mid_at_horizon: dict[int, int] = {}
    horizon_iter = iter(config.candidate_horizons_ns)
    next_horizon = next(horizon_iter, None)
    for event in future:
        if event.kind == "snapshot":
            raise PredictionDataError("label horizon crosses a snapshot/reconnect boundary")
        while next_horizon is not None and cutoff + next_horizon < event.event_time_ns:
            mid_at_horizon[next_horizon] = max(bids) + min(asks)
            next_horizon = next(horizon_iter, None)
        if event.kind == "trade":
            through = (
                event.trade_price_ticks < initial_quote
                if point.passive_side == "bid"
                else event.trade_price_ticks > initial_quote
            )
            if through and depletion_time is None:
                depletion_time = event.event_time_ns
        else:
            _apply_event(event, bids, asks)
            quote_present = initial_quote in (bids if point.passive_side == "bid" else asks)
            best = max(bids) if point.passive_side == "bid" else min(asks)
            worsened = best < initial_quote if point.passive_side == "bid" else best > initial_quote
            if (not quote_present or worsened) and depletion_time is None:
                depletion_time = event.event_time_ns
    while next_horizon is not None:
        mid_at_horizon[next_horizon] = max(bids) + min(asks)
        next_horizon = next(horizon_iter, None)
    side_sign = 1 if point.passive_side == "bid" else -1
    label: dict[str, object] = {
        "row_id": feature["row_id"],
        "symbol": point.symbol,
        "passive_side": point.passive_side,
        "target_start_exclusive_ns": cutoff,
        "label_coverage_end_ns": coverage_end_ns,
        "depletion_event_time_ns": -1 if depletion_time is None else depletion_time,
    }
    for horizon, suffix in (
        (250_000_000, "250ms"),
        (1_000_000_000, "1s"),
        (5_000_000_000, "5s"),
    ):
        label[f"quote_depletion_{suffix}"] = int(
            depletion_time is not None and depletion_time <= cutoff + horizon
        )
        future_mid2 = mid_at_horizon[horizon]
        label[f"adverse_selection_{suffix}_half_ticks"] = side_sign * (current_mid2 - future_mid2)
    return label


def build_feature_label_rows(
    events: Iterable[PredictionMarketEvent],
    decisions: Iterable[DecisionPoint],
    coverage_end_ns_by_symbol: dict[str, int],
    config: PredictionFeatureConfig,
) -> list[FeatureLabelRow]:
    event_list = list(events)
    if not event_list:
        raise PredictionDataError("prediction event stream cannot be empty")
    seen: set[int] = set()
    previous_by_symbol: dict[str, tuple[int, int]] = {}
    previous_available_by_symbol: dict[str, int] = {}
    for event in event_list:
        event.validate()
        if event.sequence in seen:
            raise PredictionDataError("prediction event sequences must be globally unique")
        seen.add(event.sequence)
        previous = previous_by_symbol.get(event.symbol)
        key = (event.event_time_ns, event.sequence)
        if previous is not None and key <= previous:
            raise PredictionDataError("events must be strictly ordered per symbol")
        previous_by_symbol[event.symbol] = key
        previous_available = previous_available_by_symbol.get(event.symbol)
        if previous_available is not None and event.available_time_ns < previous_available:
            raise PredictionDataError("event availability must be nondecreasing per symbol")
        previous_available_by_symbol[event.symbol] = event.available_time_ns
    event_list.sort(key=lambda item: (item.event_time_ns, item.sequence))
    decisions_list = list(decisions)
    if not decisions_list:
        raise PredictionDataError("at least one decision point is required")
    rows: list[FeatureLabelRow] = []
    row_ids: set[str] = set()
    for point in sorted(
        decisions_list,
        key=lambda item: (item.decision_time_ns, item.symbol, item.passive_side),
    ):
        if point.symbol not in config.symbols or point.passive_side not in {"bid", "ask"}:
            raise PredictionDataError("decision point symbol/side is invalid")
        if point.decision_time_ns <= config.observation_latency_ns:
            raise PredictionDataError("decision time must exceed observation latency")
        coverage = coverage_end_ns_by_symbol.get(point.symbol)
        if coverage is None:
            raise PredictionDataError("missing label coverage for decision symbol")
        feature = _feature_row(config, point, event_list)
        if str(feature["row_id"]) in row_ids:
            raise PredictionDataError("duplicate prediction row_id")
        row_ids.add(str(feature["row_id"]))
        label = _future_label(config, point, feature, event_list, coverage)
        rows.append(FeatureLabelRow(feature=feature, label=label))
    return rows
