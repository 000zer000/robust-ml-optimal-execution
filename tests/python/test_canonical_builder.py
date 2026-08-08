from __future__ import annotations

import gzip
import json
from decimal import Decimal
from pathlib import Path

import pytest

from robust_execution.canonical_data.builder import (
    CanonicalDataError,
    _deduplicate,
    build_canonical_dataset,
    decimal_to_units,
)
from robust_execution.canonical_data.config import load_canonical_data_config
from robust_execution.canonical_data.models import rows_to_columns
from robust_execution.canonical_data.verify import (
    CanonicalDataVerificationError,
    verify_canonical_dataset,
)

CAPTURE = Path("data/sample/validation_step13/step13-full-day-fixture/manifest.json")
REPORT = Path("results/validation/step13/step13-fixture-validation/validation-report.json")
CONFIG = Path("configs/data/binance_canonical_sample.json")


def _build(tmp_path: Path) -> Path:
    return build_canonical_dataset(
        CAPTURE,
        REPORT,
        load_canonical_data_config(CONFIG),
        tmp_path,
        dataset_id="test-canonical",
    )


def _table(manifest: Path, name: str) -> dict[str, object]:
    with gzip.open(manifest.parent / "tables" / name / "columns.json.gz", "rt") as handle:
        return json.load(handle)


def test_decimal_to_units_is_exact() -> None:
    assert decimal_to_units("100.50", Decimal("0.01"), "price") == 10050
    assert decimal_to_units("0.10000", Decimal("0.00001"), "quantity") == 10000
    with pytest.raises(CanonicalDataError):
        decimal_to_units("1.001", Decimal("0.01"), "price")
    with pytest.raises(CanonicalDataError):
        decimal_to_units("-1", Decimal("0.01"), "price")
    with pytest.raises(CanonicalDataError):
        decimal_to_units("nan", Decimal("0.01"), "price")


def test_build_and_verify_fixture(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    result = verify_canonical_dataset(manifest)
    assert result["classification"] == "sample_only_non_research"
    assert result["table_rows"] == {
        "instrument_definitions": 2,
        "source_records": 8,
        "book_snapshots": 4,
        "book_deltas": 6,
        "trades": 4,
        "duplicate_records": 0,
    }
    source = _table(manifest, "source_records")
    assert source["columns"]["canonical_message_sequence"] == list(range(8))
    trades = _table(manifest, "trades")
    assert trades["columns"]["price_ticks"] == [10050, 10050, 10060, 10040]
    assert trades["columns"]["quantity_lots"] == [10000, 20000, 15000, 25000]
    book = _table(manifest, "book_deltas")
    assert book["columns"]["side"] == ["bid", "ask", "bid", "ask", "bid", "ask"]
    assert book["columns"]["is_delete"] == [False, False, False, False, False, False]


def test_build_is_immutable(tmp_path: Path) -> None:
    _build(tmp_path)
    with pytest.raises(FileExistsError):
        _build(tmp_path)


def test_processed_tier_rejects_non_admitted_fixture(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    raw["output_tier"] = "processed"
    raw["input_policy"]["allow_structurally_valid_fixture_sample"] = False
    path = tmp_path / "processed.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataError, match="research-admitted"):
        build_canonical_dataset(
            CAPTURE,
            REPORT,
            load_canonical_data_config(path),
            tmp_path / "output",
        )


def test_tampered_table_is_detected(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    data_path = manifest.parent / "tables/trades/columns.json.gz"
    data_path.write_bytes(data_path.read_bytes() + b"tamper")
    with pytest.raises(CanonicalDataVerificationError, match="digest mismatch"):
        verify_canonical_dataset(manifest)


def test_manifest_digest_tamper_is_detected(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    value = json.loads(manifest.read_text())
    value["research_admissible"] = True
    manifest.write_text(json.dumps(value))
    with pytest.raises(CanonicalDataVerificationError, match="manifest digest"):
        verify_canonical_dataset(manifest)


def test_duplicate_policy() -> None:
    payload = '{"stream":"btcusdt@trade","data":{"e":"trade","s":"BTCUSDT","t":1}}'
    digest = "a" * 64
    base = {
        "raw_payload_utf8": payload,
        "raw_payload_sha256": digest,
        "_source_record_index": 0,
    }
    unique, duplicates = _deduplicate([base, base | {"_source_record_index": 1}])
    assert len(unique) == 1
    assert duplicates[0]["disposition"] == "exact_duplicate_dropped"
    conflict_payload = '{"stream":"btcusdt@trade","data":{"e":"trade","s":"BTCUSDT","t":1,"p":"1"}}'
    with pytest.raises(CanonicalDataError, match="conflicting duplicate"):
        _deduplicate(
            [
                base,
                base
                | {
                    "raw_payload_utf8": conflict_payload,
                    "raw_payload_sha256": "b" * 64,
                    "_source_record_index": 1,
                },
            ]
        )


def test_rows_to_columns_rejects_shape_mismatch() -> None:
    assert rows_to_columns([{"a": 1, "b": 2}], ("a", "b")) == {"a": [1], "b": [2]}
    with pytest.raises(ValueError, match="columns mismatch"):
        rows_to_columns([{"a": 1}], ("a", "b"))
