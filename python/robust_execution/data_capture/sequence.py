"""Binance diff-depth buffering, snapshot installation, and continuity diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from robust_execution.data_capture.models import SymbolDiagnostics


class SequenceError(ValueError):
    """Raised for malformed depth data or invalid snapshot content."""


class SyncState(StrEnum):
    BUFFERING = "buffering"
    SYNCHRONIZED = "synchronized"
    INVALID = "invalid"


@dataclass(frozen=True)
class DepthUpdate:
    symbol: str
    first_update_id: int
    final_update_id: int
    event_time: int
    bids: tuple[tuple[str, str], ...]
    asks: tuple[tuple[str, str], ...]


class LocalOrderBook:
    def __init__(self) -> None:
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}

    @staticmethod
    def _parse_level(level: object) -> tuple[Decimal, Decimal]:
        if not isinstance(level, list) or len(level) != 2:
            raise SequenceError("book level must be [price, quantity]")
        try:
            price = Decimal(str(level[0]))
            quantity = Decimal(str(level[1]))
        except InvalidOperation as exc:
            raise SequenceError("book level contains an invalid decimal") from exc
        if price <= 0 or quantity < 0:
            raise SequenceError("price must be positive and quantity non-negative")
        return price, quantity

    def load_snapshot(self, bids: object, asks: object) -> None:
        if not isinstance(bids, list) or not isinstance(asks, list):
            raise SequenceError("snapshot bids and asks must be arrays")
        new_bids = dict(self._parse_level(level) for level in bids)
        new_asks = dict(self._parse_level(level) for level in asks)
        if not new_bids or not new_asks:
            raise SequenceError("snapshot must contain both sides")
        self._assert_not_crossed(new_bids, new_asks)
        self.bids = new_bids
        self.asks = new_asks

    def apply(self, bids: tuple[tuple[str, str], ...], asks: tuple[tuple[str, str], ...]) -> None:
        new_bids = dict(self.bids)
        new_asks = dict(self.asks)
        for raw_price, raw_quantity in bids:
            price, quantity = self._parse_level([raw_price, raw_quantity])
            if quantity == 0:
                new_bids.pop(price, None)
            else:
                new_bids[price] = quantity
        for raw_price, raw_quantity in asks:
            price, quantity = self._parse_level([raw_price, raw_quantity])
            if quantity == 0:
                new_asks.pop(price, None)
            else:
                new_asks[price] = quantity
        if new_bids and new_asks:
            self._assert_not_crossed(new_bids, new_asks)
        self.bids = new_bids
        self.asks = new_asks

    @staticmethod
    def _assert_not_crossed(bids: dict[Decimal, Decimal], asks: dict[Decimal, Decimal]) -> None:
        if max(bids) >= min(asks):
            raise SequenceError("book is crossed or locked")

    def best_bid(self) -> Decimal | None:
        return max(self.bids) if self.bids else None

    def best_ask(self) -> Decimal | None:
        return min(self.asks) if self.asks else None


def parse_depth_update(payload: object) -> DepthUpdate:
    if not isinstance(payload, dict) or payload.get("e") != "depthUpdate":
        raise SequenceError("payload is not a Binance depthUpdate")
    symbol = payload.get("s")
    first = payload.get("U")
    final = payload.get("u")
    event_time = payload.get("E")
    if not isinstance(symbol, str) or not symbol:
        raise SequenceError("depth update symbol is missing")
    for name, value in (("U", first), ("u", final), ("E", event_time)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SequenceError(f"depth update {name} must be a non-negative integer")
    assert isinstance(first, int) and not isinstance(first, bool)
    assert isinstance(final, int) and not isinstance(final, bool)
    assert isinstance(event_time, int) and not isinstance(event_time, bool)
    if first > final:
        raise SequenceError("depth update U exceeds u")
    bids = payload.get("b")
    asks = payload.get("a")
    if not isinstance(bids, list) or not isinstance(asks, list):
        raise SequenceError("depth update b and a must be arrays")
    parsed_bids = tuple((str(level[0]), str(level[1])) for level in bids if len(level) == 2)
    parsed_asks = tuple((str(level[0]), str(level[1])) for level in asks if len(level) == 2)
    if len(parsed_bids) != len(bids) or len(parsed_asks) != len(asks):
        raise SequenceError("malformed depth level")
    return DepthUpdate(symbol, first, final, event_time, parsed_bids, parsed_asks)


class DepthSynchronizer:
    """Maintain a validated aggregate L2 book for capture diagnostics only."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.state = SyncState.BUFFERING
        self.book = LocalOrderBook()
        self.local_update_id: int | None = None
        self._buffer: list[DepthUpdate] = []
        self.diagnostics = SymbolDiagnostics(symbol=symbol)
        self._interval_start: int | None = None

    def ingest(self, update: DepthUpdate) -> str:
        if update.symbol != self.symbol:
            raise SequenceError("depth symbol does not match synchronizer")
        if self.state is SyncState.BUFFERING:
            self._buffer.append(update)
            self.diagnostics.buffered_events += 1
            return "buffered"
        if self.state is SyncState.INVALID:
            self._buffer.append(update)
            self.diagnostics.buffered_events += 1
            return "buffered_invalid"
        return self._apply_update(update)

    def install_snapshot(self, snapshot: object) -> bool:
        if not isinstance(snapshot, dict):
            raise SequenceError("snapshot must be an object")
        last = snapshot.get("lastUpdateId")
        if not isinstance(last, int) or isinstance(last, bool) or last < 0:
            raise SequenceError("snapshot lastUpdateId must be a non-negative integer")
        self.book.load_snapshot(snapshot.get("bids"), snapshot.get("asks"))
        self.diagnostics.snapshots += 1
        self._buffer = [event for event in self._buffer if event.final_update_id > last]
        if self._buffer:
            first = self._buffer[0]
            if not (first.first_update_id <= last <= first.final_update_id):
                self.state = SyncState.BUFFERING
                self.local_update_id = None
                return False
        self.local_update_id = last
        self.state = SyncState.SYNCHRONIZED
        self.diagnostics.synchronized = True
        self._interval_start = last
        buffered = list(self._buffer)
        self._buffer.clear()
        for event in buffered:
            result = self._apply_update(event)
            if result == "gap":
                return False
        return True

    def invalidate(self, *, crossed: bool = False) -> None:
        if self.state is SyncState.SYNCHRONIZED and self._interval_start is not None:
            self.diagnostics.synchronized_intervals.append(
                {
                    "first_update_id": self._interval_start,
                    "last_update_id": self.local_update_id or 0,
                }
            )
        self.state = SyncState.INVALID
        self.diagnostics.synchronized = False
        self.diagnostics.resynchronizations += 1
        if crossed:
            self.diagnostics.crossed_books += 1
        self.local_update_id = None
        self._interval_start = None
        self._buffer.clear()

    def begin_resynchronization(self) -> None:
        if self.state is SyncState.SYNCHRONIZED and self._interval_start is not None:
            self.diagnostics.synchronized_intervals.append(
                {
                    "first_update_id": self._interval_start,
                    "last_update_id": self.local_update_id or 0,
                }
            )
        self.state = SyncState.BUFFERING
        self.diagnostics.synchronized = False
        self.local_update_id = None
        self._interval_start = None
        self._buffer.clear()

    def _apply_update(self, update: DepthUpdate) -> str:
        local = self.local_update_id
        if local is None:
            self._buffer.append(update)
            self.state = SyncState.BUFFERING
            return "buffered"
        if update.final_update_id < local:
            self.diagnostics.ignored_events += 1
            return "ignored_old"
        if update.final_update_id == local:
            self.diagnostics.duplicate_events += 1
            return "duplicate"
        if update.first_update_id > local + 1:
            self.diagnostics.gaps += 1
            self.invalidate()
            self._buffer.append(update)
            return "gap"
        try:
            self.book.apply(update.bids, update.asks)
        except SequenceError:
            self.invalidate(crossed=True)
            raise
        self.local_update_id = update.final_update_id
        self.diagnostics.applied_events += 1
        if self.diagnostics.first_update_id is None:
            self.diagnostics.first_update_id = update.first_update_id
        self.diagnostics.last_update_id = update.final_update_id
        return "applied"

    def finalize(self) -> None:
        if self.state is SyncState.SYNCHRONIZED and self._interval_start is not None:
            self.diagnostics.synchronized_intervals.append(
                {
                    "first_update_id": self._interval_start,
                    "last_update_id": self.local_update_id or 0,
                }
            )
            self._interval_start = None
