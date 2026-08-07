from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Any

import jsonschema

from robust_execution.data_capture.collector import BinanceRawCollector
from robust_execution.data_capture.config import load_capture_config


ROOT = Path(__file__).resolve().parents[2]


class FakeRest:
    async def exchange_info(self, symbols: tuple[str, ...]) -> bytes:
        return json.dumps(
            {
                "symbols": [
                    {"symbol": symbol, "status": "TRADING", "filters": [{"filterType": "PRICE_FILTER"}]}
                    for symbol in symbols
                ]
            },
            separators=(",", ":"),
        ).encode()

    async def depth_snapshot(self, symbol: str, limit: int) -> bytes:
        assert limit == 5000
        return json.dumps(
            {
                "lastUpdateId": 100,
                "bids": [["99", "10"]],
                "asks": [["102", "10"]],
                "symbol_fixture": symbol,
            },
            separators=(",", ":"),
        ).encode()


class FakeWebSocket:
    remote_address = ("127.0.0.1", 443)

    def __init__(self, messages: list[str], *, fail_at_end: bool) -> None:
        self.messages = list(messages)
        self.fail_at_end = fail_at_end

    async def recv(self) -> str:
        await asyncio.sleep(0)
        if self.messages:
            return self.messages.pop(0)
        if self.fail_at_end:
            raise ConnectionError("forced reconnect")
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")

    async def close(self, code: int = 1000, reason: str = "") -> None:
        return None


class FakeContext:
    def __init__(self, socket: FakeWebSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> FakeWebSocket:
        return self.socket

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class ScriptedConnector:
    def __init__(self, scripts: list[tuple[list[str], bool]]) -> None:
        self.scripts = list(scripts)
        self.urls: list[str] = []

    def __call__(self, url: str) -> FakeContext:
        self.urls.append(url)
        messages, fail = self.scripts.pop(0)
        return FakeContext(FakeWebSocket(messages, fail_at_end=fail))


def combined(stream: str, data: dict[str, Any]) -> str:
    return json.dumps({"stream": stream, "data": data}, separators=(",", ":"))


def depth(symbol: str, first: int, final: int) -> str:
    lower = symbol.lower()
    return combined(
        f"{lower}@depth@100ms",
        {
            "e": "depthUpdate",
            "E": 1_000_000 + final,
            "s": symbol,
            "U": first,
            "u": final,
            "b": [["100", "2"]],
            "a": [["101", "3"]],
        },
    )


def trade(symbol: str, trade_id: int) -> str:
    return combined(
        f"{symbol.lower()}@trade",
        {
            "e": "trade",
            "E": 2_000_000 + trade_id,
            "s": symbol,
            "t": trade_id,
            "p": "100.5",
            "q": "0.1",
            "T": 2_000_000 + trade_id,
            "m": False,
            "M": True,
        },
    )


def test_offline_capture_forced_reconnect_and_manifest(tmp_path: Path) -> None:
    payload = json.loads((ROOT / "configs/data/binance_capture_pilot.json").read_text())
    payload["storage"]["output_root"] = str(tmp_path / "raw")
    payload["storage"]["segment_max_messages"] = 3
    payload["pilot"]["reconnect_backoff_seconds"] = 0
    config_path = tmp_path / "capture.json"
    config_path.write_text(json.dumps(payload))
    config = load_capture_config(config_path)

    first = [depth("BTCUSDT", 100, 101), trade("BTCUSDT", 1)]
    second = [
        depth("BTCUSDT", 100, 101),
        depth("ETHUSDT", 100, 101),
        trade("ETHUSDT", 2),
        depth("BTCUSDT", 102, 102),
    ]
    connector = ScriptedConnector([(first, True), (second, False)])
    collector = BinanceRawCollector(config, rest=FakeRest(), websocket_connector=connector)
    manifest_path = asyncio.run(
        collector.run(duration_seconds=259200, max_messages=6, run_id="offline-fixture")
    )
    manifest = json.loads(manifest_path.read_text())
    schema = json.loads(
        (ROOT / "schemas/data/raw-capture-manifest-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(manifest)

    assert manifest["status"] == "pilot_incomplete"
    assert manifest["pilot_72h_complete"] is False
    assert manifest["total_messages"] == 6
    assert len(manifest["connections"]) == 2
    assert manifest["connections"][0]["outcome"] == "transport_error"
    assert manifest["exact_raw_payload_preserved"] is True
    assert manifest["publication"]["raw_market_data_public"] is False
    assert len(connector.urls) == 2

    segments = [item for item in manifest["artifacts"] if "segment-" in item["relative_path"]]
    assert sum(item["record_count"] for item in segments) == 6
    restored: list[str] = []
    for segment in segments:
        with gzip.open(manifest_path.parent / segment["relative_path"], "rt", encoding="utf-8") as handle:
            restored.extend(json.loads(line)["raw_payload_utf8"] for line in handle)
    assert restored == first + second


def test_exchange_info_missing_symbol_aborts_with_manifest(tmp_path: Path) -> None:
    class BadRest(FakeRest):
        async def exchange_info(self, symbols: tuple[str, ...]) -> bytes:
            return b'{"symbols":[]}'

    payload = json.loads((ROOT / "configs/data/binance_capture_pilot.json").read_text())
    payload["storage"]["output_root"] = str(tmp_path / "raw")
    config_path = tmp_path / "capture.json"
    config_path.write_text(json.dumps(payload))
    config = load_capture_config(config_path)
    collector = BinanceRawCollector(
        config, rest=BadRest(), websocket_connector=ScriptedConnector([])
    )
    try:
        asyncio.run(collector.run(duration_seconds=1, run_id="bad-exchange-info"))
    except Exception as exc:
        assert "missing BTCUSDT" in str(exc)
    else:
        raise AssertionError("expected capture failure")
    manifest = json.loads((tmp_path / "raw/bad-exchange-info/manifest.json").read_text())
    assert manifest["status"] == "aborted"
    assert manifest["total_messages"] == 0
