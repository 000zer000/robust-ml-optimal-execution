"""Deterministic synthetic Step 21 feature/label validation tape."""

from __future__ import annotations

from robust_execution.prediction.models import BookUpdate, DecisionPoint, PredictionMarketEvent

NS = 1_000_000_000


def validation_fixture() -> tuple[list[PredictionMarketEvent], list[DecisionPoint], dict[str, int]]:
    events: list[PredictionMarketEvent] = []
    sequence = 0

    def add_symbol(symbol: str, offset: int, second_regime_depletes: bool) -> None:
        nonlocal sequence

        def snap(
            t_ms: int,
            bids: tuple[tuple[int, int], ...],
            asks: tuple[tuple[int, int], ...],
        ) -> None:
            nonlocal sequence
            t = t_ms * 1_000_000
            events.append(
                PredictionMarketEvent(
                    sequence,
                    symbol,
                    "snapshot",
                    t,
                    t + 100_000_000,
                    bids=bids,
                    asks=asks,
                )
            )
            sequence += 1

        def depth(t_ms: int, *updates: BookUpdate) -> None:
            nonlocal sequence
            t = t_ms * 1_000_000
            events.append(
                PredictionMarketEvent(
                    sequence,
                    symbol,
                    "depth",
                    t,
                    t + 100_000_000,
                    updates=tuple(updates),
                )
            )
            sequence += 1

        def trade(t_ms: int, price: int, quantity: int, buyer_is_maker: bool) -> None:
            nonlocal sequence
            t = t_ms * 1_000_000
            events.append(
                PredictionMarketEvent(
                    sequence,
                    symbol,
                    "trade",
                    t,
                    t + 100_000_000,
                    trade_price_ticks=price,
                    trade_quantity_lots=quantity,
                    buyer_is_maker=buyer_is_maker,
                )
            )
            sequence += 1

        b = 100 + offset
        snap(
            0,
            ((b, 100), (b - 1, 200), (b - 2, 300)),
            ((b + 1, 120), (b + 2, 220), (b + 3, 320)),
        )
        trade(500, b, 10, True)
        depth(1_000, BookUpdate("bid", b, 110))
        trade(2_000, b + 1, 20, False)
        depth(3_000, BookUpdate("ask", b + 1, 100))
        depth(4_000, BookUpdate("bid", b - 1, 240), BookUpdate("ask", b + 2, 200))
        trade(5_800, b, 15, True)
        # Decision at 6 s has source cutoff 5.9 s. Ask depletes inside 250 ms;
        # bid depletes after 1 s but within 5 s.
        depth(6_050, BookUpdate("ask", b + 1, 0))
        depth(6_300, BookUpdate("ask", b + 1, 80))
        trade(6_600, b + 1, 12, False)
        depth(7_200, BookUpdate("bid", b, 0))
        depth(7_350, BookUpdate("bid", b, 90))
        depth(8_000, BookUpdate("bid", b, 105), BookUpdate("ask", b + 1, 95))
        trade(8_800, b + 1, 18, False)
        # Decision at 9 s has source cutoff 8.9 s. Bid depletes quickly; ask is only
        # traded through after one second, but within five seconds.
        if second_regime_depletes:
            depth(9_050, BookUpdate("bid", b, 0))
            depth(9_250, BookUpdate("bid", b, 85))
            depth(9_600, BookUpdate("bid", b, 100), BookUpdate("ask", b + 1, 110))
            trade(10_500, b + 3, 9, False)
            depth(
                11_000,
                BookUpdate("bid", b, 0),
                BookUpdate("ask", b + 1, 0),
                BookUpdate("bid", b + 1, 95),
                BookUpdate("ask", b + 2, 105),
            )
            trade(12_000, b + 2, 11, True)
        else:
            depth(9_050, BookUpdate("bid", b, 103))
            depth(9_600, BookUpdate("ask", b + 1, 107))
            trade(10_500, b + 1, 9, False)
            depth(11_000, BookUpdate("bid", b, 98), BookUpdate("ask", b + 1, 102))
            trade(12_000, b, 11, True)
        # Sentinel after every decision's 5 s target horizon. Mutation here must not
        # affect earlier features or labels.
        trade(14_100, b + 2, 7, False)

    add_symbol("BTCUSDT", 0, True)
    add_symbol("ETHUSDT", 100, False)
    events.sort(key=lambda item: (item.event_time_ns, item.sequence))
    decisions = [
        DecisionPoint(symbol, decision * NS, side)
        for symbol in ("BTCUSDT", "ETHUSDT")
        for decision in (6, 9)
        for side in ("bid", "ask")
    ]
    coverage = {"BTCUSDT": 15 * NS, "ETHUSDT": 15 * NS}
    return events, decisions, coverage
