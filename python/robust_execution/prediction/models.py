"""Normalized Step 21 market events and prediction rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["bid", "ask"]
EventKind = Literal["snapshot", "depth", "trade"]


class PredictionDataError(RuntimeError):
    """Raised when prediction data would violate causality or market-state invariants."""


@dataclass(frozen=True)
class BookUpdate:
    side: Side
    price_ticks: int
    quantity_lots: int


@dataclass(frozen=True)
class PredictionMarketEvent:
    sequence: int
    symbol: str
    kind: EventKind
    event_time_ns: int
    available_time_ns: int
    bids: tuple[tuple[int, int], ...] = ()
    asks: tuple[tuple[int, int], ...] = ()
    updates: tuple[BookUpdate, ...] = ()
    trade_price_ticks: int = 0
    trade_quantity_lots: int = 0
    buyer_is_maker: bool = False

    def validate(self) -> None:
        if self.sequence < 0 or not self.symbol or self.symbol != self.symbol.upper():
            raise PredictionDataError("event sequence/symbol is invalid")
        if self.event_time_ns < 0 or self.available_time_ns < self.event_time_ns:
            raise PredictionDataError("event timestamps violate causality")
        if self.kind == "snapshot":
            if not self.bids or not self.asks or self.updates or self.trade_quantity_lots:
                raise PredictionDataError("snapshot payload is malformed")
            for price, quantity in (*self.bids, *self.asks):
                if price <= 0 or quantity <= 0:
                    raise PredictionDataError("snapshot levels must be positive")
        elif self.kind == "depth":
            if not self.updates or self.bids or self.asks or self.trade_quantity_lots:
                raise PredictionDataError("depth payload is malformed")
            for update in self.updates:
                if update.price_ticks <= 0 or update.quantity_lots < 0:
                    raise PredictionDataError("depth update is invalid")
        elif self.kind == "trade":
            if self.bids or self.asks or self.updates:
                raise PredictionDataError("trade cannot contain book payloads")
            if self.trade_price_ticks <= 0 or self.trade_quantity_lots <= 0:
                raise PredictionDataError("trade price/quantity must be positive")
        else:
            raise PredictionDataError("unsupported prediction event kind")


@dataclass(frozen=True)
class DecisionPoint:
    symbol: str
    decision_time_ns: int
    passive_side: Side


@dataclass(frozen=True)
class FeatureLabelRow:
    feature: dict[str, object]
    label: dict[str, object]
