"""Production Binance REST and WebSocket transport adapters."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RestTransport(Protocol):
    async def exchange_info(self, symbols: tuple[str, ...]) -> bytes: ...

    async def depth_snapshot(self, symbol: str, limit: int) -> bytes: ...


class WebSocketLike(Protocol):
    remote_address: object

    async def recv(self) -> str | bytes: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class WebSocketContext(Protocol):
    async def __aenter__(self) -> WebSocketLike: ...

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool | None: ...


class WebSocketConnector(Protocol):
    def __call__(self, url: str) -> WebSocketContext: ...


class BinanceRestTransport:
    def __init__(self, base_url: str, timeout_seconds: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def exchange_info(self, symbols: tuple[str, ...]) -> bytes:
        query = urlencode({"symbols": json.dumps(list(symbols), separators=(",", ":"))})
        return await asyncio.to_thread(self._get, f"/api/v3/exchangeInfo?{query}")

    async def depth_snapshot(self, symbol: str, limit: int) -> bytes:
        query = urlencode({"symbol": symbol, "limit": limit})
        return await asyncio.to_thread(self._get, f"/api/v3/depth?{query}")

    def _get(self, path: str) -> bytes:
        request = Request(
            f"{self.base_url}{path}",
            headers={"User-Agent": "robust-execution-step12/0.9", "X-MBX-TIME-UNIT": "MICROSECOND"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()


def default_websocket_connector(url: str) -> WebSocketContext:
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "live capture requires websockets==16.0; install requirements/capture.lock"
        ) from exc
    return connect(
        url,
        ping_interval=None,
        ping_timeout=None,
        close_timeout=10,
        max_queue=4096,
        compression=None,
    )
