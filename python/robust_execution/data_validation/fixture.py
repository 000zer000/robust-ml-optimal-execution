"""Deterministic Step 13 full-day capture fixture."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from robust_execution import __version__
from robust_execution.data_capture.models import (
    CaptureManifest,
    ConnectionRecord,
    RawMessageRecord,
    canonical_json_bytes,
    sha256_hex,
)
from robust_execution.data_capture.storage import (
    GzipJsonlSegmentWriter,
    artifact_as_dict,
    write_immutable_gzip_blob,
    write_immutable_json,
)


def _wrapped(stream: str, data: dict[str, object]) -> str:
    return json.dumps({"stream": stream, "data": data}, separators=(",", ":"))


def generate_step13_capture_fixture(output_root: Path) -> Path:
    run_id = "step13-full-day-fixture"
    root = output_root / run_id
    if root.exists():
        raise FileExistsError(f"fixture already exists: {root}")
    root.mkdir(parents=True)
    day = "2027-01-15"
    day_start_ns = int(datetime(2027, 1, 15, tzinfo=UTC).timestamp() * 1_000_000_000)
    day_end_ns = day_start_ns + 86_400_000_000_000
    connection_id = "connection-0000"

    config = {
        "schema_version": 1,
        "venue_id": "binance_spot",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "websocket_base": "wss://data-stream.binance.vision",
        "rest_base": "https://data-api.binance.vision",
        "streams": {"depth": "@depth@100ms", "trade": "@trade"},
        "timestamp_unit": "MICROSECOND",
        "snapshot_limit": 5000,
        "storage": {
            "output_root": "data/raw/binance_spot",
            "compression": "gzip",
            "segment_max_messages": 1000000,
            "segment_max_uncompressed_bytes": 134217728,
            "fsync_each_record": False,
            "fsync_interval_messages": 10000,
        },
        "pilot": {
            "required_duration_seconds": 259200,
            "rotate_before_seconds": 82800,
            "reconnect_backoff_seconds": 1.0,
            "receive_timeout_seconds": 30.0,
            "max_reconnects": 100,
        },
        "research_specification_changed": False,
        "paid_data_required": False,
    }
    config_bytes = canonical_json_bytes(config) + b"\n"
    exchange_info = {
        "timezone": "UTC",
        "serverTime": day_start_ns // 1_000_000,
        "symbols": [
            {"symbol": symbol, "status": "TRADING", "baseAsset": symbol[:-4], "quoteAsset": "USDT"}
            for symbol in ("BTCUSDT", "ETHUSDT")
        ],
    }
    contract = {
        "venue_id": "binance_spot",
        "symbols": {
            "BTCUSDT": {"status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"},
            "ETHUSDT": {"status": "TRADING", "baseAsset": "ETH", "quoteAsset": "USDT"},
        },
    }
    runtime = {
        "python": "fixture",
        "implementation": "deterministic",
        "platform": "fixture",
        "byteorder": "little",
    }
    artifacts: list[dict[str, object]] = []
    for relative, data, content_type in (
        (
            "metadata/exchange-info.json.gz",
            canonical_json_bytes(exchange_info) + b"\n",
            "application/json; profile=binance-exchange-info",
        ),
        (
            "metadata/symbol-contract.json.gz",
            canonical_json_bytes(contract) + b"\n",
            "application/json; profile=binance-symbol-contract-v1",
        ),
        (
            "metadata/capture-config.json.gz",
            config_bytes,
            "application/json; profile=raw-capture-config-v1",
        ),
        (
            "metadata/runtime.json.gz",
            canonical_json_bytes(runtime) + b"\n",
            "application/json; profile=capture-runtime-v1",
        ),
    ):
        artifact = write_immutable_gzip_blob(root / relative, data, content_type=content_type)
        artifacts.append(artifact_as_dict(artifact, root))

    snapshot = {
        "lastUpdateId": 100,
        "bids": [["100.00", "5.00000"]],
        "asks": [["101.00", "5.00000"]],
    }
    for symbol in ("BTCUSDT", "ETHUSDT"):
        artifact = write_immutable_gzip_blob(
            root / "snapshots" / symbol / f"{connection_id}-100.json.gz",
            canonical_json_bytes(snapshot) + b"\n",
            content_type="application/json; profile=binance-depth-snapshot",
        )
        artifacts.append(artifact_as_dict(artifact, root))

    schedule: list[tuple[int, str, dict[str, object]]] = [
        (
            day_start_ns + 1_000_000_000,
            "btcusdt@depth@100ms",
            {
                "e": "depthUpdate",
                "E": (day_start_ns + 900_000_000) // 1000,
                "s": "BTCUSDT",
                "U": 100,
                "u": 101,
                "b": [["100.00", "6.00000"]],
                "a": [["101.00", "5.00000"]],
            },
        ),
        (
            day_start_ns + 2_000_000_000,
            "btcusdt@trade",
            {
                "e": "trade",
                "E": (day_start_ns + 1_900_000_000) // 1000,
                "s": "BTCUSDT",
                "t": 1001,
                "p": "100.50",
                "q": "0.10000",
                "T": (day_start_ns + 1_900_000_000) // 1000,
                "m": False,
                "M": True,
            },
        ),
        (
            day_start_ns + 3_000_000_000,
            "ethusdt@depth@100ms",
            {
                "e": "depthUpdate",
                "E": (day_start_ns + 2_900_000_000) // 1000,
                "s": "ETHUSDT",
                "U": 100,
                "u": 101,
                "b": [["100.00", "7.00000"]],
                "a": [["101.00", "5.00000"]],
            },
        ),
        (
            day_start_ns + 4_000_000_000,
            "ethusdt@trade",
            {
                "e": "trade",
                "E": (day_start_ns + 3_900_000_000) // 1000,
                "s": "ETHUSDT",
                "t": 2001,
                "p": "100.50",
                "q": "0.20000",
                "T": (day_start_ns + 3_900_000_000) // 1000,
                "m": True,
                "M": True,
            },
        ),
        (
            day_start_ns + 43_200_000_000_000,
            "btcusdt@depth@100ms",
            {
                "e": "depthUpdate",
                "E": (day_start_ns + 43_199_900_000_000) // 1000,
                "s": "BTCUSDT",
                "U": 102,
                "u": 102,
                "b": [["100.00", "5.50000"]],
                "a": [],
            },
        ),
        (
            day_start_ns + 43_201_000_000_000,
            "ethusdt@depth@100ms",
            {
                "e": "depthUpdate",
                "E": (day_start_ns + 43_200_900_000_000) // 1000,
                "s": "ETHUSDT",
                "U": 102,
                "u": 102,
                "b": [],
                "a": [["101.00", "6.00000"]],
            },
        ),
        (
            day_end_ns - 2_000_000_000,
            "btcusdt@trade",
            {
                "e": "trade",
                "E": (day_end_ns - 2_100_000_000) // 1000,
                "s": "BTCUSDT",
                "t": 1002,
                "p": "100.60",
                "q": "0.15000",
                "T": (day_end_ns - 2_100_000_000) // 1000,
                "m": False,
                "M": True,
            },
        ),
        (
            day_end_ns - 1_000_000_000,
            "ethusdt@trade",
            {
                "e": "trade",
                "E": (day_end_ns - 1_100_000_000) // 1000,
                "s": "ETHUSDT",
                "t": 2002,
                "p": "100.40",
                "q": "0.25000",
                "T": (day_end_ns - 1_100_000_000) // 1000,
                "m": True,
                "M": True,
            },
        ),
    ]
    writer = GzipJsonlSegmentWriter(root / "raw" / day / "segment-000000.jsonl.gz")
    total_raw = 0
    for index, (received, stream, payload) in enumerate(schedule):
        raw_text = _wrapped(stream, payload)
        raw_bytes = raw_text.encode("utf-8")
        writer.append(
            RawMessageRecord(
                schema_version=1,
                run_id=run_id,
                connection_id=connection_id,
                message_index=index,
                received_utc_ns=received,
                received_monotonic_ns=10_000_000_000 + index * 1_000_000,
                stream=stream,
                symbol=str(payload["s"]),
                event_type=str(payload["e"]),
                raw_payload_sha256=sha256_hex(raw_bytes),
                raw_payload_utf8=raw_text,
            )
        )
        total_raw += len(raw_bytes)
    segment = writer.seal()
    artifacts.append(artifact_as_dict(segment, root))

    connection = ConnectionRecord(
        connection_id=connection_id,
        endpoint="wss://data-stream.binance.vision/stream?fixture",
        started_utc_ns=day_start_ns,
        ended_utc_ns=day_end_ns,
        outcome="fixture_complete",
        messages=len(schedule),
        selected_remote="fixture",
    )

    def artifact_size(item: dict[str, object], field: str) -> int:
        value = item.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(f"fixture artifact {field} must be a non-negative integer")
        return value

    total_compressed = sum(artifact_size(item, "compressed_bytes") for item in artifacts)
    total_uncompressed = sum(artifact_size(item, "uncompressed_bytes") for item in artifacts)
    manifest = CaptureManifest(
        schema_version=1,
        step=12,
        run_id=run_id,
        venue_id="binance_spot",
        data_origin="synthetic_transport_fixture",
        symbols=["BTCUSDT", "ETHUSDT"],
        status="complete",
        started_utc_ns=day_start_ns,
        ended_utc_ns=day_end_ns,
        planned_duration_seconds=259200,
        actual_duration_seconds=86400.0,
        pilot_72h_complete=False,
        websocket_url="wss://data-stream.binance.vision/stream?fixture",
        rest_base="https://data-api.binance.vision",
        compression="gzip",
        exact_raw_payload_preserved=True,
        research_specification_changed=False,
        paid_data_used=False,
        software_version=__version__,
        runtime=runtime,
        capture_config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        total_messages=len(schedule),
        total_raw_payload_bytes=total_raw,
        total_uncompressed_bytes=total_uncompressed,
        total_compressed_bytes=total_compressed,
        connections=[asdict(connection)],
        artifacts=artifacts,
        symbol_diagnostics=[],
        errors=[],
        publication={
            "raw_market_data_public": False,
            "credentials_stored": False,
            "redistribution_cleared": False,
        },
    )
    write_immutable_json(root / "manifest.json", manifest.to_dict())
    write_immutable_json(
        root / "manifest.sha256.json",
        {"sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()},
    )
    return root / "manifest.json"
