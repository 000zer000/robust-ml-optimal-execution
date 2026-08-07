from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from robust_execution import cli
from robust_execution.data_capture.collector import BinanceRawCollector, CaptureError, resolve_hostnames
from robust_execution.data_capture.config import CaptureConfigurationError, load_capture_config
from robust_execution.data_capture.offline_fixture import write_offline_fixture
from robust_execution.data_capture.sequence import DepthSynchronizer, SequenceError, parse_depth_update
from robust_execution.data_capture.storage import GzipJsonlSegmentWriter, StorageError
from robust_execution.data_capture.transport import BinanceRestTransport, default_websocket_connector
from robust_execution.data_capture.verify import CaptureVerificationError, verify_capture_manifest


ROOT = Path(__file__).resolve().parents[2]


def config_in(tmp_path: Path) -> Path:
    payload = json.loads((ROOT / "configs/data/binance_capture_pilot.json").read_text())
    payload["storage"]["output_root"] = str(tmp_path / "raw")
    payload["pilot"]["reconnect_backoff_seconds"] = 0
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(payload))
    return path


def test_offline_fixture_module_is_deterministic(tmp_path: Path) -> None:
    config = load_capture_config(config_in(tmp_path))
    first = asyncio.run(write_offline_fixture(config, tmp_path / "one"))
    second = asyncio.run(write_offline_fixture(config, tmp_path / "two"))
    result = verify_capture_manifest(first)
    assert result["messages"] == 6
    assert json.loads(first.read_text())["data_origin"] == "synthetic_transport_fixture"

    def tree_hash(root: Path) -> dict[str, str]:
        base = root.parent
        return {
            str(path.relative_to(base)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.parent.rglob("*"))
            if path.is_file()
        }

    first_hashes = {
        path.relative_to(first.parent).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in first.parent.rglob("*")
        if path.is_file()
    }
    second_hashes = {
        path.relative_to(second.parent).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in second.parent.rglob("*")
        if path.is_file()
    }
    assert first_hashes == second_hashes
    assert tree_hash(first) != {}  # exercise stable traversal helper input


def test_collector_constructor_and_argument_guards(tmp_path: Path) -> None:
    config = load_capture_config(config_in(tmp_path))
    with pytest.raises(CaptureError, match="data_origin"):
        BinanceRawCollector(config, data_origin="invented")
    collector = BinanceRawCollector(config)
    with pytest.raises(CaptureError, match="duration"):
        asyncio.run(collector.run(duration_seconds=0))
    with pytest.raises(CaptureError, match="max_messages"):
        asyncio.run(collector.run(duration_seconds=1, max_messages=0))
    existing = config.storage.output_root / "exists"
    existing.mkdir(parents=True)
    with pytest.raises(CaptureError, match="already exists"):
        asyncio.run(collector.run(duration_seconds=1, run_id="exists"))


def test_decode_bytes_and_invalid_combined_payload() -> None:
    raw = '{"stream":"btcusdt@trade","data":{"e":"trade","s":"BTCUSDT"}}'
    stream, symbol, event_type, data = BinanceRawCollector._decode_message(raw)
    assert (stream, symbol, event_type) == ("btcusdt@trade", "BTCUSDT", "trade")
    assert isinstance(data, dict)
    stream, symbol, event_type, _ = BinanceRawCollector._decode_message("[]")
    assert (stream, symbol, event_type) == ("raw", None, None)
    with pytest.raises(CaptureError, match="stream name"):
        BinanceRawCollector._decode_message('{"stream":1,"data":{}}')


def test_exchange_info_validation_errors_and_summary(tmp_path: Path) -> None:
    config = load_capture_config(config_in(tmp_path))
    collector = BinanceRawCollector(config)
    with pytest.raises(CaptureError, match="valid JSON"):
        collector._validate_exchange_info(b"not-json")
    with pytest.raises(CaptureError, match="symbols array"):
        collector._validate_exchange_info(b"{}")
    payload: dict[str, Any] = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "HALT", "filters": [{}]},
            {"symbol": "ETHUSDT", "status": "TRADING", "filters": [{}]},
        ]
    }
    with pytest.raises(CaptureError, match="not TRADING"):
        collector._validate_exchange_info(json.dumps(payload).encode())
    payload["symbols"][0]["status"] = "TRADING"
    payload["symbols"][0]["filters"] = []
    with pytest.raises(CaptureError, match="no exchange filters"):
        collector._validate_exchange_info(json.dumps(payload).encode())
    payload["symbols"][0]["filters"] = [{}]
    summary = collector._validate_exchange_info(json.dumps(payload).encode())
    assert summary["captured_from_exchange_info"] is True


def test_config_low_level_type_and_url_errors(tmp_path: Path) -> None:
    original = json.loads((ROOT / "configs/data/binance_capture_pilot.json").read_text())
    mutations = [
        ("root", []),
        ("schema_version", True),
        ("symbols", ["BTCUSDT", 1]),
        ("streams", []),
        ("storage", []),
        ("storage.output_root", ""),
        ("websocket_base", "https://wrong.example"),
        ("rest_base", "https://host/path?query=1"),
        ("pilot.receive_timeout_seconds", 0),
        ("storage.fsync_each_record", "false"),
    ]
    for index, (field, value) in enumerate(mutations):
        payload: Any = json.loads(json.dumps(original))
        if field == "root":
            payload = value
        elif "." in field:
            first, second = field.split(".")
            payload[first][second] = value
        else:
            payload[field] = value
        path = tmp_path / f"bad-{index}.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(CaptureConfigurationError):
            load_capture_config(path)
    bad_json = tmp_path / "broken.json"
    bad_json.write_text("{")
    with pytest.raises(CaptureConfigurationError, match="cannot load"):
        load_capture_config(bad_json)


def test_sequence_additional_failure_paths() -> None:
    sync = DepthSynchronizer("BTCUSDT")
    with pytest.raises(SequenceError, match="symbol"):
        sync.ingest(
            parse_depth_update(
                {"e": "depthUpdate", "E": 1, "s": "ETHUSDT", "U": 1, "u": 1, "b": [], "a": []}
            )
        )
    with pytest.raises(SequenceError, match="object"):
        sync.install_snapshot([])
    with pytest.raises(SequenceError, match="lastUpdateId"):
        sync.install_snapshot({"lastUpdateId": "1", "bids": [], "asks": []})
    with pytest.raises(SequenceError, match="both sides"):
        sync.install_snapshot({"lastUpdateId": 1, "bids": [], "asks": []})
    with pytest.raises(SequenceError, match="invalid decimal"):
        sync.install_snapshot({"lastUpdateId": 1, "bids": [["x", "1"]], "asks": [["2", "1"]]})
    with pytest.raises(SequenceError, match="non-negative"):
        sync.install_snapshot({"lastUpdateId": 1, "bids": [["1", "-1"]], "asks": [["2", "1"]]})


def test_storage_abort_and_double_seal(tmp_path: Path) -> None:
    writer = GzipJsonlSegmentWriter(tmp_path / "segment.gz")
    writer.abort()
    writer.abort()
    assert not (tmp_path / "segment.gz").exists()
    stale = tmp_path / "stale.gz.partial"
    stale.write_bytes(b"")
    with pytest.raises(StorageError, match="stale partial"):
        GzipJsonlSegmentWriter(tmp_path / "stale.gz")


def test_rest_transport_and_websocket_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok":true}'

    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float) -> Response:
        calls.append((request, timeout))
        return Response()

    monkeypatch.setattr("robust_execution.data_capture.transport.urlopen", fake_urlopen)
    transport = BinanceRestTransport("https://data-api.binance.vision", timeout_seconds=3)
    assert asyncio.run(transport.exchange_info(("BTCUSDT",))) == b'{"ok":true}'
    assert asyncio.run(transport.depth_snapshot("BTCUSDT", 5000)) == b'{"ok":true}'
    assert len(calls) == 2
    context = default_websocket_connector("wss://data-stream.binance.vision/ws/test")
    assert hasattr(context, "__aenter__")


def test_resolve_hostnames_success_and_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = load_capture_config(config_in(tmp_path))
    counter = {"calls": 0}

    def fake_getaddrinfo(host: str, port: int) -> list[tuple[Any, ...]]:
        counter["calls"] += 1
        if counter["calls"] == 2:
            raise OSError("dns failed")
        return [(2, 1, 6, "", ("203.0.113.1", port))]

    monkeypatch.setattr("robust_execution.data_capture.collector.socket.getaddrinfo", fake_getaddrinfo)
    result = resolve_hostnames(config)
    assert result["rest"]["status"] == "resolved"
    assert result["websocket"]["status"] == "failed"


def test_cli_new_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = config_in(tmp_path)
    monkeypatch.setattr(cli, "resolve_hostnames", lambda config: {"rest": {"status": "resolved"}, "websocket": {"status": "resolved"}})
    assert cli.main(["capture-network-check", str(config_path)]) == 0

    class FakeCollector:
        def __init__(self, config: object) -> None:
            del config

        async def run(self, **kwargs: object) -> Path:
            assert kwargs["max_messages"] == 2
            return tmp_path / "manifest.json"

    monkeypatch.setattr(cli, "BinanceRawCollector", FakeCollector)
    assert cli.main(["capture-binance", str(config_path), "--max-messages", "2"]) == 0
    output = capsys.readouterr().out
    assert "manifest.json" in output


def test_verify_manifest_error_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(CaptureVerificationError, match="cannot read"):
        verify_capture_manifest(missing)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("[]")
    with pytest.raises(CaptureVerificationError, match="unsupported"):
        verify_capture_manifest(manifest)
    manifest.write_text(json.dumps({"schema_version": 1, "step": 11, "research_specification_changed": False, "paid_data_used": False}))
    with pytest.raises(CaptureVerificationError, match="governance"):
        verify_capture_manifest(manifest)
