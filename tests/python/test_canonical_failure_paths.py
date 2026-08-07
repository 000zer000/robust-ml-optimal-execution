from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import types

import pytest

from robust_execution.canonical_data.builder import (
    CanonicalDataError,
    _build_rows,
    _deduplicate,
    _parquet_status,
    _read_gzip_json,
    _read_json,
    _selected_days,
    _snapshot_rows,
    decimal_to_units,
)
from robust_execution.canonical_data.config import (
    CanonicalDataConfigurationError,
    load_canonical_data_config,
)
from robust_execution.canonical_data.parquet import ParquetExportError, write_parquet_table
from robust_execution.canonical_data.verify import (
    CanonicalDataVerificationError,
    verify_canonical_dataset,
)
from robust_execution.canonical_data import build_canonical_dataset

CAPTURE = Path("data/sample/validation_step13/step13-full-day-fixture/manifest.json")
REPORT = Path("results/validation/step13/step13-fixture-validation/validation-report.json")
CONFIG = Path("configs/data/binance_canonical_sample.json")


def _build(tmp_path: Path) -> Path:
    return build_canonical_dataset(
        CAPTURE,
        REPORT,
        load_canonical_data_config(CONFIG),
        tmp_path,
        dataset_id="failure-fixture",
    )


def _rewrite_manifest(path: Path, mutate) -> dict[str, object]:
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    path.with_name("dataset-manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True, separators=(",", ":")) + "\n"
    )
    return value


def _rewrite_table(manifest: Path, name: str, mutate) -> None:
    value = json.loads(manifest.read_text())
    item = next(entry for entry in value["tables"] if entry["table_name"] == name)
    path = manifest.parent / item["data_relative_path"]
    with gzip.open(path, "rt") as handle:
        table = json.load(handle)
    mutate(table)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
            handle.write(json.dumps(table, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    item["data_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.with_name("dataset-manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}, sort_keys=True, separators=(",", ":")) + "\n"
    )


def test_config_parse_failures(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    with pytest.raises(CanonicalDataConfigurationError, match="cannot load"):
        load_canonical_data_config(bad)
    bad.write_text("[]")
    with pytest.raises(CanonicalDataConfigurationError, match="schema_version"):
        load_canonical_data_config(bad)
    raw = json.loads(CONFIG.read_text())
    raw["input_policy"] = []
    bad.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError, match="must be objects"):
        load_canonical_data_config(bad)
    raw = json.loads(CONFIG.read_text())
    raw["instruments"] = []
    bad.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError, match="exactly two"):
        load_canonical_data_config(bad)
    raw = json.loads(CONFIG.read_text())
    raw["instruments"][0]["source"] = ""
    bad.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError, match="source"):
        load_canonical_data_config(bad)
    raw = json.loads(CONFIG.read_text())
    raw["instruments"][0]["quantity_increment"] = "not-decimal"
    bad.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError, match="not a decimal"):
        load_canonical_data_config(bad)
    raw = json.loads(CONFIG.read_text())
    raw["format_policy"]["compression"] = "none"
    bad.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError, match="compression"):
        load_canonical_data_config(bad)


def test_low_level_reader_and_selection_failures(tmp_path: Path) -> None:
    with pytest.raises(CanonicalDataError, match="cannot read"):
        _read_json(tmp_path / "missing.json")
    broken = tmp_path / "broken.json.gz"
    broken.write_bytes(b"not gzip")
    with pytest.raises(CanonicalDataError, match="cannot read"):
        _read_gzip_json(broken)
    config = load_canonical_data_config(CONFIG)
    with pytest.raises(CanonicalDataError, match="days"):
        _selected_days({}, config)
    with pytest.raises(CanonicalDataError, match="structurally valid"):
        _selected_days({"days": []}, config)


def test_decimal_and_payload_failure_paths() -> None:
    with pytest.raises(CanonicalDataError, match="not a decimal"):
        decimal_to_units(object(), config_increment := __import__("decimal").Decimal("0.01"), "x")
    valid = {
        "raw_payload_utf8": '{"stream":"x","data":{"e":"unknown","s":"BTCUSDT"}}',
        "raw_payload_sha256": "a" * 64,
        "_source_record_index": 0,
    }
    with pytest.raises(CanonicalDataError, match="unsupported"):
        _deduplicate([valid])
    with pytest.raises(CanonicalDataError, match="cannot be parsed"):
        _deduplicate([valid | {"raw_payload_utf8": "{"}])


def test_build_rows_rejects_bad_depth_shape() -> None:
    config = load_canonical_data_config(CONFIG)
    record = {
        "raw_payload_utf8": json.dumps({"stream": "x", "data": {"e": "depthUpdate", "E": 1, "s": "BTCUSDT", "U": 1, "u": 1, "b": "bad", "a": []}}),
        "symbol": "BTCUSDT",
        "run_id": "r",
        "_source_record_index": 0,
        "_source_relative_path": "x",
        "_source_line_number": 1,
        "raw_payload_sha256": "a" * 64,
        "connection_id": "c",
        "message_index": 0,
        "stream": "x",
        "received_utc_ns": 1,
        "received_monotonic_ns": 1,
    }
    with pytest.raises(CanonicalDataError, match="depth levels"):
        _build_rows([record], config, "d")
    wrapper = json.loads(record["raw_payload_utf8"])
    wrapper["data"]["b"] = [["1"]]
    record["raw_payload_utf8"] = json.dumps(wrapper)
    with pytest.raises(CanonicalDataError, match="depth level"):
        _build_rows([record], config, "d")


def test_snapshot_parser_rejects_unknown_connection(tmp_path: Path) -> None:
    root = tmp_path / "capture"
    (root / "snapshots/BTCUSDT").mkdir(parents=True)
    manifest = {
        "run_id": "r",
        "connections": [],
        "artifacts": [{"relative_path": "snapshots/BTCUSDT/unknown-100.json.gz"}],
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    with (root / "snapshots/BTCUSDT/unknown-100.json.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
            handle.write(b'{"lastUpdateId":100,"bids":[],"asks":[]}')
    with pytest.raises(CanonicalDataError, match="not in manifest"):
        _snapshot_rows(path, load_canonical_data_config(CONFIG), "d", {"2027-01-15"})


def test_parquet_status_and_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = load_canonical_data_config(CONFIG)
    status = _parquet_status(config)
    assert status["required"] is False

    fake_pa = types.ModuleType("pyarrow")
    fake_pa.__version__ = "25.0.0"
    fake_pa.bool_ = lambda: "bool"
    fake_pa.int64 = lambda: "int64"
    fake_pa.string = lambda: "string"
    fake_pa.array = lambda values, type=None: list(values)

    class FakeTable:
        def __init__(self, arrays):
            self.arrays = arrays
            self.num_rows = len(next(iter(arrays.values()))) if arrays else 0

    fake_pa.table = lambda arrays: FakeTable(arrays)
    fake_pq = types.ModuleType("pyarrow.parquet")
    fake_pq.write_table = lambda table, path, **kwargs: Path(path).write_bytes(b"PAR1fake")
    fake_pa.parquet = fake_pq
    monkeypatch.setitem(sys.modules, "pyarrow", fake_pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", fake_pq)
    artifact = write_parquet_table(
        tmp_path / "table.parquet",
        [{"a": 1, "b": True, "c": "x"}],
        {"columns": [
            {"name": "a", "logical_type": "int64"},
            {"name": "b", "logical_type": "bool"},
            {"name": "c", "logical_type": "utf8"},
        ]},
        ("a", "b", "c"),
    )
    assert artifact["rows"] == 1
    with pytest.raises(ParquetExportError, match="overwrite"):
        write_parquet_table(
            tmp_path / "table.parquet", [], {"columns": []}, ()
        )
    fake_pa.__version__ = "24.0.0"
    with pytest.raises(ParquetExportError, match="exactly"):
        write_parquet_table(tmp_path / "other.parquet", [], {"columns": []}, ())


def test_verify_failure_matrix(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    _rewrite_manifest(manifest, lambda value: value.update({"research_specification_changed": True}))
    with pytest.raises(CanonicalDataVerificationError, match="specification"):
        verify_canonical_dataset(manifest)

    manifest = _build(tmp_path / "b")
    _rewrite_manifest(manifest, lambda value: value.update({"missing_events_repaired": True}))
    with pytest.raises(CanonicalDataVerificationError, match="repaired"):
        verify_canonical_dataset(manifest)

    manifest = _build(tmp_path / "c")
    _rewrite_manifest(manifest, lambda value: value["tables"].pop())
    with pytest.raises(CanonicalDataVerificationError, match="six"):
        verify_canonical_dataset(manifest)

    manifest = _build(tmp_path / "d")
    _rewrite_table(manifest, "trades", lambda table: table["columns"]["trade_id"].pop())
    with pytest.raises(CanonicalDataVerificationError, match="column lengths"):
        verify_canonical_dataset(manifest)

    manifest = _build(tmp_path / "e")
    _rewrite_manifest(manifest, lambda value: value.update({"unique_messages": 999}))
    with pytest.raises(CanonicalDataVerificationError, match="source-record"):
        verify_canonical_dataset(manifest)

    manifest = _build(tmp_path / "f")
    _rewrite_manifest(manifest, lambda value: value.update({"dataset_classification": "unknown"}))
    with pytest.raises(CanonicalDataVerificationError, match="classification"):
        verify_canonical_dataset(manifest)


def test_processed_dataset_writes_pinned_parquet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil
    import robust_execution.canonical_data.builder as builder_module

    capture_root = tmp_path / "live-capture"
    validation_root = tmp_path / "live-validation"
    shutil.copytree(CAPTURE.parent, capture_root)
    shutil.copytree(REPORT.parent, validation_root)
    capture_manifest = capture_root / "manifest.json"
    capture = json.loads(capture_manifest.read_text())
    capture["data_origin"] = "live_binance"
    capture["pilot_72h_complete"] = True
    capture["actual_duration_seconds"] = 259200.0
    capture["status"] = "complete"
    capture_manifest.write_text(
        json.dumps(capture, sort_keys=True, separators=(",", ":")) + "\n"
    )
    capture_manifest.with_name("manifest.sha256.json").write_text(
        json.dumps(
            {"sha256": hashlib.sha256(capture_manifest.read_bytes()).hexdigest()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    validation_report = validation_root / "validation-report.json"
    report = json.loads(validation_report.read_text())
    report["data_origin"] = "live_binance"
    report["source_manifest_sha256"] = hashlib.sha256(capture_manifest.read_bytes()).hexdigest()
    report["days"][0]["admission_status"] = "admitted"
    report["days"][0]["reasons"] = []
    report["summary"]["admitted_days"] = 1
    report["summary"]["non_admissible_valid_days"] = 0
    validation_report.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    )
    validation_report.with_name("validation-report.sha256.json").write_text(
        json.dumps(
            {"sha256": hashlib.sha256(validation_report.read_bytes()).hexdigest()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    config_raw = json.loads(CONFIG.read_text())
    config_raw["output_tier"] = "processed"
    config_raw["input_policy"]["allow_structurally_valid_fixture_sample"] = False
    config_path = tmp_path / "processed.json"
    config_path.write_text(json.dumps(config_raw))

    fake_pa = types.ModuleType("pyarrow")
    fake_pa.__version__ = "25.0.0"
    fake_pa.bool_ = lambda: "bool"
    fake_pa.int64 = lambda: "int64"
    fake_pa.string = lambda: "string"
    fake_pa.array = lambda values, type=None: list(values)

    class FakeTable:
        def __init__(self, arrays):
            self.num_rows = len(next(iter(arrays.values()))) if arrays else 0

    fake_pa.table = lambda arrays: FakeTable(arrays)
    fake_pq = types.ModuleType("pyarrow.parquet")
    fake_pq.write_table = lambda table, path, **kwargs: Path(path).write_bytes(b"PAR1" + bytes([table.num_rows]))
    fake_pa.parquet = fake_pq
    monkeypatch.setitem(sys.modules, "pyarrow", fake_pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", fake_pq)
    monkeypatch.setattr(builder_module.importlib.util, "find_spec", lambda name: object())

    manifest = build_canonical_dataset(
        capture_manifest,
        validation_report,
        load_canonical_data_config(config_path),
        tmp_path / "processed-output",
        dataset_id="processed-canonical",
    )
    result = verify_canonical_dataset(manifest)
    assert result["classification"] == "research_processed"
    payload = json.loads(manifest.read_text())
    assert payload["parquet"]["written"] is True
    assert len(payload["parquet"]["artifacts"]) == 6
