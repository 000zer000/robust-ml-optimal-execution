"""Deterministic synthetic transport used to validate Step 12 without market claims."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from robust_execution.data_capture.collector import BinanceRawCollector
from robust_execution.data_capture.config import CaptureConfig
from robust_execution.data_capture.transport import (
    WebSocketConnector,
    WebSocketContext,
    WebSocketLike,
)


class DeterministicClock:
    def __init__(self, start: int, step: int) -> None:
        self.value = start - step
        self.step = step

    def __call__(self) -> int:
        self.value += self.step
        return self.value


class FixtureRestTransport:
    async def exchange_info(self, symbols: tuple[str, ...]) -> bytes:
        return json.dumps(
            {
                "timezone": "UTC",
                "serverTime": 1_700_000_000_000_000,
                "symbols": [
                    {
                        "symbol": symbol,
                        "status": "TRADING",
                        "baseAsset": symbol.removesuffix("USDT"),
                        "quoteAsset": "USDT",
                        "baseAssetPrecision": 8,
                        "quoteAssetPrecision": 8,
                        "orderTypes": ["LIMIT", "MARKET"],
                        "defaultSelfTradePreventionMode": "EXPIRE_MAKER",
                        "allowedSelfTradePreventionModes": ["EXPIRE_MAKER"],
                        "filters": [
                            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                            {"filterType": "LOT_SIZE", "stepSize": "0.00001000"},
                            {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                        ],
                    }
                    for symbol in symbols
                ],
            },
            separators=(",", ":"),
        ).encode()

    async def depth_snapshot(self, symbol: str, limit: int) -> bytes:
        if limit != 5000:
            raise AssertionError("fixture expects the selected snapshot limit")
        return json.dumps(
            {
                "lastUpdateId": 100,
                "bids": [["99.00", "10.00000"]],
                "asks": [["102.00", "10.00000"]],
                "fixture_symbol": symbol,
            },
            separators=(",", ":"),
        ).encode()


class FixtureSocket(WebSocketLike):
    remote_address = ("192.0.2.10", 443)

    def __init__(self, messages: list[str], fail_at_end: bool) -> None:
        self.messages = list(messages)
        self.fail_at_end = fail_at_end

    async def recv(self) -> str:
        await asyncio.sleep(0)
        if self.messages:
            return self.messages.pop(0)
        if self.fail_at_end:
            raise ConnectionError("fixture-forced-reconnect")
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        return None


class FixtureContext(WebSocketContext):
    def __init__(self, socket: FixtureSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> FixtureSocket:
        return self.socket

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FixtureConnector(WebSocketConnector):
    def __init__(self) -> None:
        self.scripts = [
            ([depth("BTCUSDT", 100, 101), trade("BTCUSDT", 1)], True),
            (
                [
                    depth("BTCUSDT", 100, 101),
                    depth("ETHUSDT", 100, 101),
                    trade("ETHUSDT", 2),
                    depth("BTCUSDT", 102, 102),
                ],
                False,
            ),
        ]

    def __call__(self, url: str) -> FixtureContext:
        del url
        messages, fail_at_end = self.scripts.pop(0)
        return FixtureContext(FixtureSocket(messages, fail_at_end))


def combined(stream: str, data: dict[str, Any]) -> str:
    return json.dumps({"stream": stream, "data": data}, separators=(",", ":"))


def depth(symbol: str, first: int, final: int) -> str:
    return combined(
        f"{symbol.lower()}@depth@100ms",
        {
            "e": "depthUpdate",
            "E": 1_700_000_000_000_000 + final,
            "s": symbol,
            "U": first,
            "u": final,
            "b": [["100.00", "2.00000"]],
            "a": [["101.00", "3.00000"]],
        },
    )


def trade(symbol: str, trade_id: int) -> str:
    return combined(
        f"{symbol.lower()}@trade",
        {
            "e": "trade",
            "E": 1_700_000_100_000_000 + trade_id,
            "s": symbol,
            "t": trade_id,
            "p": "100.50",
            "q": "0.10000",
            "T": 1_700_000_100_000_000 + trade_id,
            "m": False,
            "M": True,
        },
    )


async def write_offline_fixture(config: CaptureConfig, output_root: Path) -> Path:
    fixture_config = CaptureConfig(
        schema_version=config.schema_version,
        venue_id=config.venue_id,
        symbols=config.symbols,
        websocket_base=config.websocket_base,
        rest_base=config.rest_base,
        depth_stream_suffix=config.depth_stream_suffix,
        trade_stream_suffix=config.trade_stream_suffix,
        timestamp_unit=config.timestamp_unit,
        snapshot_limit=config.snapshot_limit,
        storage=type(config.storage)(
            output_root=config.storage.output_root,
            compression=config.storage.compression,
            segment_max_messages=3,
            segment_max_uncompressed_bytes=config.storage.segment_max_uncompressed_bytes,
            fsync_each_record=False,
            fsync_interval_messages=2,
        ),
        pilot=type(config.pilot)(
            required_duration_seconds=config.pilot.required_duration_seconds,
            rotate_before_seconds=config.pilot.rotate_before_seconds,
            reconnect_backoff_seconds=0.0,
            receive_timeout_seconds=config.pilot.receive_timeout_seconds,
            max_reconnects=2,
        ),
        research_specification_changed=False,
        paid_data_required=False,
    )
    collector = BinanceRawCollector(
        fixture_config,
        rest=FixtureRestTransport(),
        websocket_connector=FixtureConnector(),
        clock_utc_ns=DeterministicClock(1_800_000_000_000_000_000, 1_000_000),
        clock_monotonic_ns=DeterministicClock(10_000_000_000, 1_000_000),
        data_origin="synthetic_transport_fixture",
        output_root_override=output_root,
    )
    return await collector.run(
        duration_seconds=259200,
        max_messages=6,
        run_id="step12-offline-fixture",
    )
