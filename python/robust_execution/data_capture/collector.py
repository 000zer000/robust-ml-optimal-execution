"""Asynchronous raw Binance Spot capture with immutable manifests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import socket
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from robust_execution import __version__
from robust_execution.data_capture.config import CaptureConfig
from robust_execution.data_capture.models import (
    CaptureManifest,
    ConnectionRecord,
    RawMessageRecord,
    canonical_json_bytes,
    sha256_hex,
)
from robust_execution.data_capture.sequence import (
    DepthSynchronizer,
    SequenceError,
    parse_depth_update,
)
from robust_execution.data_capture.storage import (
    GzipJsonlSegmentWriter,
    artifact_as_dict,
    verify_segment,
    write_immutable_gzip_blob,
    write_immutable_json,
)
from robust_execution.data_capture.transport import (
    BinanceRestTransport,
    RestTransport,
    WebSocketConnector,
    default_websocket_connector,
)


class CaptureError(RuntimeError):
    """Raised when the raw capture cannot continue safely."""


def utc_now_ns() -> int:
    return time.time_ns()


def _run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"binance-spot-{stamp}-{uuid4().hex[:12]}"


class BinanceRawCollector:
    def __init__(
        self,
        config: CaptureConfig,
        *,
        rest: RestTransport | None = None,
        websocket_connector: WebSocketConnector = default_websocket_connector,
        clock_utc_ns: Any = utc_now_ns,
        clock_monotonic_ns: Any = time.monotonic_ns,
        data_origin: str = "live_binance",
        output_root_override: Path | None = None,
    ) -> None:
        self.config = config
        self.rest = rest or BinanceRestTransport(config.rest_base)
        self.websocket_connector = websocket_connector
        self.clock_utc_ns = clock_utc_ns
        self.clock_monotonic_ns = clock_monotonic_ns
        if data_origin not in {"live_binance", "synthetic_transport_fixture"}:
            raise CaptureError("unsupported data_origin")
        self.data_origin = data_origin
        self.output_root = output_root_override or config.storage.output_root

    async def run(
        self,
        *,
        duration_seconds: float | None = None,
        max_messages: int | None = None,
        run_id: str | None = None,
    ) -> Path:
        planned = self.config.pilot.required_duration_seconds
        requested = float(planned if duration_seconds is None else duration_seconds)
        if requested <= 0:
            raise CaptureError("duration_seconds must be positive")
        if max_messages is not None and max_messages <= 0:
            raise CaptureError("max_messages must be positive")

        identifier = run_id or _run_id()
        root = self.output_root / identifier
        if root.exists():
            raise CaptureError(f"capture run already exists: {root}")
        root.mkdir(parents=True)
        started_utc = self.clock_utc_ns()
        started_monotonic = self.clock_monotonic_ns()
        deadline = started_monotonic + int(requested * 1_000_000_000)
        synchronizers = {symbol: DepthSynchronizer(symbol) for symbol in self.config.symbols}
        artifacts: list[dict[str, Any]] = []
        connections: list[ConnectionRecord] = []
        errors: list[dict[str, Any]] = []
        total_messages = 0
        total_raw_bytes = 0
        segment_index = 0
        writer: GzipJsonlSegmentWriter | None = None
        writer_day: str | None = None
        capture_config_bytes = canonical_json_bytes(self.config.to_dict()) + b"\n"
        runtime = {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "byteorder": sys.byteorder,
        }

        def open_writer(day: str) -> GzipJsonlSegmentWriter:
            nonlocal segment_index
            path = root / "raw" / day / f"segment-{segment_index:06d}.jsonl.gz"
            segment_index += 1
            return GzipJsonlSegmentWriter(
                path,
                fsync_each_record=self.config.storage.fsync_each_record,
                fsync_interval_messages=self.config.storage.fsync_interval_messages,
            )

        status = "aborted"
        try:
            exchange_info = await self.rest.exchange_info(self.config.symbols)
            symbol_contract = self._validate_exchange_info(exchange_info)
            artifact = write_immutable_gzip_blob(
                root / "metadata" / "exchange-info.json.gz",
                exchange_info,
                content_type="application/json; profile=binance-exchange-info",
            )
            artifacts.append(artifact_as_dict(artifact, root))
            contract_artifact = write_immutable_gzip_blob(
                root / "metadata" / "symbol-contract.json.gz",
                canonical_json_bytes(symbol_contract) + b"\n",
                content_type="application/json; profile=binance-symbol-contract-v1",
            )
            artifacts.append(artifact_as_dict(contract_artifact, root))
            config_artifact = write_immutable_gzip_blob(
                root / "metadata" / "capture-config.json.gz",
                capture_config_bytes,
                content_type="application/json; profile=raw-capture-config-v1",
            )
            artifacts.append(artifact_as_dict(config_artifact, root))
            runtime_artifact = write_immutable_gzip_blob(
                root / "metadata" / "runtime.json.gz",
                canonical_json_bytes(runtime) + b"\n",
                content_type="application/json; profile=capture-runtime-v1",
            )
            artifacts.append(artifact_as_dict(runtime_artifact, root))
            reconnects = 0
            while self.clock_monotonic_ns() < deadline:
                if max_messages is not None and total_messages >= max_messages:
                    break
                if reconnects > self.config.pilot.max_reconnects:
                    raise CaptureError("maximum reconnect count exceeded")
                connection_id = f"connection-{len(connections):04d}"
                connection = ConnectionRecord(
                    connection_id=connection_id,
                    endpoint=self.config.combined_stream_url(),
                    started_utc_ns=self.clock_utc_ns(),
                )
                connections.append(connection)
                try:
                    async with self.websocket_connector(connection.endpoint) as websocket:
                        connection.selected_remote = str(getattr(websocket, "remote_address", None))
                        for synchronizer in synchronizers.values():
                            synchronizer.begin_resynchronization()
                        snapshot_tasks = {
                            symbol: asyncio.create_task(
                                self._fetch_snapshot(root, connection_id, symbol, artifacts)
                            )
                            for symbol in self.config.symbols
                        }
                        connection_started = self.clock_monotonic_ns()
                        while self.clock_monotonic_ns() < deadline:
                            if max_messages is not None and total_messages >= max_messages:
                                break
                            elapsed = (self.clock_monotonic_ns() - connection_started) / 1e9
                            if elapsed >= self.config.pilot.rotate_before_seconds:
                                connection.outcome = "rotated_before_24h"
                                break
                            await self._install_ready_snapshots(snapshot_tasks, synchronizers)
                            try:
                                raw_message = await asyncio.wait_for(
                                    websocket.recv(),
                                    timeout=self.config.pilot.receive_timeout_seconds,
                                )
                            except TimeoutError:
                                continue
                            if isinstance(raw_message, bytes):
                                raw_bytes = raw_message
                                raw_text = raw_message.decode("utf-8")
                            else:
                                raw_text = raw_message
                                raw_bytes = raw_text.encode("utf-8")
                            received_utc = self.clock_utc_ns()
                            received_monotonic = self.clock_monotonic_ns()
                            stream, symbol, event_type, payload = self._decode_message(raw_text)
                            day = (
                                datetime.fromtimestamp(received_utc / 1_000_000_000, tz=UTC)
                                .date()
                                .isoformat()
                            )
                            if writer is None or writer_day != day:
                                if writer is not None:
                                    sealed = writer.seal()
                                    verify_segment(Path(sealed.relative_path))
                                    artifacts.append(artifact_as_dict(sealed, root))
                                writer = open_writer(day)
                                writer_day = day
                            record = RawMessageRecord(
                                schema_version=1,
                                run_id=identifier,
                                connection_id=connection_id,
                                message_index=connection.messages,
                                received_utc_ns=received_utc,
                                received_monotonic_ns=received_monotonic,
                                stream=stream,
                                symbol=symbol,
                                event_type=event_type,
                                raw_payload_sha256=sha256_hex(raw_bytes),
                                raw_payload_utf8=raw_text,
                            )
                            if writer is None:
                                raise CaptureError("raw segment writer was not initialized")
                            writer.append(record)
                            connection.messages += 1
                            total_messages += 1
                            total_raw_bytes += len(raw_bytes)
                            if event_type == "depthUpdate" and symbol in synchronizers:
                                try:
                                    result = synchronizers[symbol].ingest(
                                        parse_depth_update(payload)
                                    )
                                    if result == "gap":
                                        snapshot_tasks[symbol] = asyncio.create_task(
                                            self._fetch_snapshot(
                                                root, connection_id, symbol, artifacts
                                            )
                                        )
                                except SequenceError as exc:
                                    synchronizers[symbol].diagnostics.malformed_events += 1
                                    errors.append(
                                        {
                                            "type": "depth_validation",
                                            "connection_id": connection_id,
                                            "symbol": symbol,
                                            "message_index": connection.messages - 1,
                                            "detail": str(exc),
                                        }
                                    )
                                    synchronizers[symbol].begin_resynchronization()
                                    snapshot_tasks[symbol] = asyncio.create_task(
                                        self._fetch_snapshot(root, connection_id, symbol, artifacts)
                                    )
                            if event_type == "serverShutdown":
                                connection.outcome = "server_shutdown"
                                break
                            if (
                                writer.records >= self.config.storage.segment_max_messages
                                or writer.uncompressed_bytes
                                >= self.config.storage.segment_max_uncompressed_bytes
                            ):
                                sealed = writer.seal()
                                verify_segment(Path(sealed.relative_path))
                                artifacts.append(artifact_as_dict(sealed, root))
                                writer = None
                                writer_day = None
                        for task in snapshot_tasks.values():
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*snapshot_tasks.values(), return_exceptions=True)
                        if connection.outcome == "open":
                            connection.outcome = "completed_or_limit_reached"
                except asyncio.CancelledError:
                    connection.outcome = "cancelled"
                    raise
                except Exception as exc:  # network boundary; recorded before retry
                    connection.outcome = "transport_error"
                    code = getattr(exc, "code", None)
                    reason = getattr(exc, "reason", None)
                    connection.close_code = code if isinstance(code, int) else None
                    connection.close_reason = (
                        str(reason) if reason else f"{type(exc).__name__}: {exc}"
                    )
                    transport_detail = connection.close_reason.lower()
                    error_type = (
                        "ping_pong_failure"
                        if "ping" in transport_detail or "pong" in transport_detail
                        else "transport"
                    )
                    errors.append(
                        {
                            "type": error_type,
                            "connection_id": connection_id,
                            "detail": connection.close_reason,
                        }
                    )
                    reconnects += 1
                    if reconnects > self.config.pilot.max_reconnects:
                        raise CaptureError("maximum reconnect count exceeded") from exc
                    if self.config.pilot.reconnect_backoff_seconds:
                        await asyncio.sleep(self.config.pilot.reconnect_backoff_seconds)
                finally:
                    connection.ended_utc_ns = self.clock_utc_ns()
            status = (
                "complete"
                if requested >= planned and self.clock_monotonic_ns() >= deadline
                else "pilot_incomplete"
            )
        except asyncio.CancelledError:
            status = "aborted"
            raise
        except Exception as exc:
            status = "aborted"
            errors.append(
                {
                    "type": "capture_abort",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            if isinstance(exc, CaptureError):
                raise
            raise CaptureError(f"capture aborted: {type(exc).__name__}: {exc}") from exc
        finally:
            ended_utc = self.clock_utc_ns()
            ended_monotonic = self.clock_monotonic_ns()
            if writer is not None:
                if writer.records:
                    sealed = writer.seal()
                    verify_segment(Path(sealed.relative_path))
                    artifacts.append(artifact_as_dict(sealed, root))
                else:
                    writer.abort()
            for synchronizer in synchronizers.values():
                synchronizer.finalize()
            manifest_path = root / "manifest.json"
            if not manifest_path.exists():
                total_compressed = sum(int(item["compressed_bytes"]) for item in artifacts)
                total_uncompressed = sum(int(item["uncompressed_bytes"]) for item in artifacts)
                manifest = CaptureManifest(
                    schema_version=1,
                    step=12,
                    run_id=identifier,
                    venue_id=self.config.venue_id,
                    data_origin=self.data_origin,
                    symbols=list(self.config.symbols),
                    status=status,
                    started_utc_ns=started_utc,
                    ended_utc_ns=ended_utc,
                    planned_duration_seconds=planned,
                    actual_duration_seconds=max(0.0, (ended_monotonic - started_monotonic) / 1e9),
                    pilot_72h_complete=(
                        status == "complete" and self.data_origin == "live_binance"
                    ),
                    websocket_url=self.config.combined_stream_url(),
                    rest_base=self.config.rest_base,
                    compression=self.config.storage.compression,
                    exact_raw_payload_preserved=True,
                    research_specification_changed=False,
                    paid_data_used=False,
                    software_version=__version__,
                    runtime=runtime,
                    capture_config_sha256=hashlib.sha256(capture_config_bytes).hexdigest(),
                    total_messages=total_messages,
                    total_raw_payload_bytes=total_raw_bytes,
                    total_uncompressed_bytes=total_uncompressed,
                    total_compressed_bytes=total_compressed,
                    connections=[asdict(item) for item in connections],
                    artifacts=artifacts,
                    symbol_diagnostics=[
                        asdict(synchronizers[symbol].diagnostics) for symbol in self.config.symbols
                    ],
                    errors=errors,
                    publication={
                        "raw_market_data_public": False,
                        "credentials_stored": False,
                        "redistribution_cleared": False,
                    },
                )
                write_immutable_json(manifest_path, manifest.to_dict())
                digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                write_immutable_json(root / "manifest.sha256.json", {"sha256": digest})
        return root / "manifest.json"

    async def _fetch_snapshot(
        self,
        root: Path,
        connection_id: str,
        symbol: str,
        artifacts: list[dict[str, Any]],
    ) -> tuple[str, object]:
        raw = await self.rest.depth_snapshot(symbol, self.config.snapshot_limit)
        parsed = json.loads(raw)
        last = parsed.get("lastUpdateId") if isinstance(parsed, dict) else "unknown"
        path = root / "snapshots" / symbol / f"{connection_id}-{last}.json.gz"
        artifact = write_immutable_gzip_blob(
            path, raw, content_type="application/json; profile=binance-depth-snapshot"
        )
        artifacts.append(artifact_as_dict(artifact, root))
        return symbol, parsed

    @staticmethod
    async def _install_ready_snapshots(
        tasks: dict[str, asyncio.Task[tuple[str, object]]],
        synchronizers: dict[str, DepthSynchronizer],
    ) -> None:
        for symbol, task in list(tasks.items()):
            if not task.done():
                continue
            del tasks[symbol]
            resolved_symbol, snapshot = task.result()
            if not synchronizers[resolved_symbol].install_snapshot(snapshot):
                raise CaptureError(f"snapshot does not overlap buffered depth range for {symbol}")

    @staticmethod
    def _decode_message(raw_text: str) -> tuple[str, str | None, str | None, object]:
        payload = json.loads(raw_text)
        if isinstance(payload, dict) and "stream" in payload and "data" in payload:
            stream = payload["stream"]
            data = payload["data"]
        else:
            stream = "raw"
            data = payload
        if not isinstance(stream, str):
            raise CaptureError("combined stream name is not a string")
        symbol = data.get("s") if isinstance(data, dict) else None
        event_type = data.get("e") if isinstance(data, dict) else None
        if symbol is not None and not isinstance(symbol, str):
            symbol = None
        if event_type is not None and not isinstance(event_type, str):
            event_type = None
        return stream, symbol, event_type, data

    def _validate_exchange_info(self, raw: bytes) -> dict[str, object]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CaptureError("exchangeInfo is not valid JSON") from exc
        symbols = payload.get("symbols") if isinstance(payload, dict) else None
        if not isinstance(symbols, list):
            raise CaptureError("exchangeInfo symbols array is missing")
        by_name = {item.get("symbol"): item for item in symbols if isinstance(item, dict)}
        selected: list[dict[str, object]] = []
        fields = (
            "symbol",
            "status",
            "baseAsset",
            "quoteAsset",
            "baseAssetPrecision",
            "quoteAssetPrecision",
            "orderTypes",
            "icebergAllowed",
            "ocoAllowed",
            "quoteOrderQtyMarketAllowed",
            "allowTrailingStop",
            "cancelReplaceAllowed",
            "amendAllowed",
            "defaultSelfTradePreventionMode",
            "allowedSelfTradePreventionModes",
            "filters",
        )
        for expected in self.config.symbols:
            item = by_name.get(expected)
            if not isinstance(item, dict):
                raise CaptureError(f"exchangeInfo is missing {expected}")
            if item.get("status") != "TRADING":
                raise CaptureError(f"{expected} is not TRADING")
            filters = item.get("filters")
            if not isinstance(filters, list) or not filters:
                raise CaptureError(f"{expected} has no exchange filters")
            selected.append({key: item[key] for key in fields if key in item})
        return {
            "schema_version": 1,
            "venue_id": self.config.venue_id,
            "captured_from_exchange_info": True,
            "symbols": selected,
        }


def resolve_hostnames(config: CaptureConfig) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for name, host in (
        ("rest", config.rest_base.split("//", 1)[1]),
        ("websocket", config.websocket_base.split("//", 1)[1]),
    ):
        try:
            addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443)})
            results[name] = {"host": host, "addresses": addresses, "status": "resolved"}
        except OSError as exc:
            results[name] = {"host": host, "status": "failed", "error": str(exc)}
    return results
