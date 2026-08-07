from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
from typing import Callable

import pytest

from robust_execution.data_validation.config import load_data_validation_config
from robust_execution.data_validation.validator import DataValidationError, validate_capture_data
from robust_execution.data_validation.verify import (
    DataValidationVerificationError,
    verify_data_validation_report,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data/sample/validation_step13/step13-full-day-fixture"
CONFIG = ROOT / "configs/data/binance_raw_validation.json"


def _rewrite_segment(root: Path, mutate: Callable[[list[dict[str, object]]], None]) -> None:
    segment = root / "raw/2027-01-15/segment-000000.jsonl.gz"
    with gzip.open(segment, "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    mutate(records)
    for record in records:
        raw = str(record["raw_payload_utf8"]).encode("utf-8")
        record["raw_payload_sha256"] = hashlib.sha256(raw).hexdigest()
    raw_lines = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for record in records
    )
    with segment.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as compressed:
            compressed.write(raw_lines)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for artifact in manifest["artifacts"]:
        if artifact["relative_path"] == "raw/2027-01-15/segment-000000.jsonl.gz":
            compressed = segment.read_bytes()
            artifact["sha256"] = hashlib.sha256(compressed).hexdigest()
            artifact["compressed_bytes"] = len(compressed)
            artifact["uncompressed_bytes"] = len(raw_lines)
            artifact["record_count"] = len(records)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (root / "manifest.sha256.json").write_text(
        json.dumps({"sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "capture"
    shutil.copytree(FIXTURE, target)
    return target


def _run(root: Path, output: Path, validation_id: str = "test") -> dict[str, object]:
    report_path = validate_capture_data(
        root / "manifest.json",
        load_data_validation_config(CONFIG),
        output,
        validation_id=validation_id,
    )
    return json.loads(report_path.read_text())


def test_full_day_fixture_is_structurally_valid_but_not_admissible(tmp_path: Path) -> None:
    report = _run(FIXTURE, tmp_path / "out")
    day = report["days"][0]
    assert day["structural_status"] == "valid"
    assert day["admission_status"] == "fixture_valid_not_admissible"
    assert day["reasons"] == ["non_live_fixture_origin", "live_72h_pilot_not_complete"]
    assert report["summary"] == {
        "admitted_days": 0,
        "non_admissible_valid_days": 1,
        "quarantined_days": 0,
        "structurally_valid_days": 1,
    }


def test_committed_validation_report_verifies() -> None:
    result = verify_data_validation_report(
        ROOT / "results/validation/step13/step13-fixture-validation/validation-report.json"
    )
    assert result["days"] == 1
    assert result["admitted_days"] == 0


@pytest.mark.parametrize("variant", ["gap", "crossed", "negative_trade", "stream", "index", "utc_reverse"])
def test_semantic_corruption_is_quarantined(tmp_path: Path, variant: str) -> None:
    root = _copy_fixture(tmp_path)

    def mutate(records: list[dict[str, object]]) -> None:
        if variant == "gap":
            wrapper = json.loads(str(records[4]["raw_payload_utf8"]))
            wrapper["data"]["U"] = 104
            wrapper["data"]["u"] = 104
            records[4]["raw_payload_utf8"] = json.dumps(wrapper, separators=(",", ":"))
        elif variant == "crossed":
            wrapper = json.loads(str(records[4]["raw_payload_utf8"]))
            wrapper["data"]["b"] = [["102.00", "1.0"]]
            records[4]["raw_payload_utf8"] = json.dumps(wrapper, separators=(",", ":"))
        elif variant == "negative_trade":
            wrapper = json.loads(str(records[1]["raw_payload_utf8"]))
            wrapper["data"]["q"] = "-1"
            records[1]["raw_payload_utf8"] = json.dumps(wrapper, separators=(",", ":"))
        elif variant == "stream":
            records[1]["stream"] = "ethusdt@trade"
        elif variant == "index":
            records[3]["message_index"] = 9
        elif variant == "utc_reverse":
            records[3]["received_utc_ns"] = int(records[2]["received_utc_ns"]) - 1

    _rewrite_segment(root, mutate)
    report = _run(root, tmp_path / "out", variant)
    assert report["days"][0]["admission_status"] == "quarantined"
    assert report["issue_counts"]["critical"] >= 1
    quarantine = json.loads(
        (tmp_path / "out" / variant / "quarantine-manifest.json").read_text()
    )
    assert quarantine["issues"]
    assert quarantine["quarantined_days"] == ["2027-01-15"]


def test_capture_manifest_tamper_fails_before_validation(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    manifest = root / "manifest.json"
    manifest.write_text(manifest.read_text().replace("BTCUSDT", "BADUSDT", 1))
    with pytest.raises(DataValidationError, match="source capture verification failed"):
        _run(root, tmp_path / "out")


def test_validation_outputs_are_create_only(tmp_path: Path) -> None:
    _run(FIXTURE, tmp_path / "out", "same")
    with pytest.raises(DataValidationError, match="already exists"):
        _run(FIXTURE, tmp_path / "out", "same")


def test_report_tamper_is_detected(tmp_path: Path) -> None:
    report_path = validate_capture_data(
        FIXTURE / "manifest.json",
        load_data_validation_config(CONFIG),
        tmp_path,
        validation_id="tamper",
    )
    payload = json.loads(report_path.read_text())
    payload["missing_events_repaired"] = True
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationVerificationError):
        verify_data_validation_report(report_path)


def test_step13_fixture_generator_is_deterministic(tmp_path: Path) -> None:
    from robust_execution.data_validation.fixture import generate_step13_capture_fixture
    from robust_execution.data_capture.verify import verify_capture_manifest

    first = generate_step13_capture_fixture(tmp_path / "first")
    second = generate_step13_capture_fixture(tmp_path / "second")
    assert verify_capture_manifest(first)["messages"] == 8
    assert verify_capture_manifest(second)["messages"] == 8
    first_files = {
        str(path.relative_to(first.parent)): path.read_bytes()
        for path in first.parent.rglob("*")
        if path.is_file()
    }
    second_files = {
        str(path.relative_to(second.parent)): path.read_bytes()
        for path in second.parent.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files
    with pytest.raises(FileExistsError):
        generate_step13_capture_fixture(tmp_path / "first")


def _rewrite_validation_report(report_path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    payload = json.loads(report_path.read_text())
    mutate(payload)
    report_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    report_path.with_name("validation-report.sha256.json").write_text(
        json.dumps(
            {"sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "variant",
    [
        "unsupported",
        "spec_changed",
        "repaired",
        "source_unverified",
        "days_invalid",
        "summary_mismatch",
        "bad_admitted_day",
        "quarantine_mismatch",
    ],
)
def test_report_semantic_inconsistencies_are_rejected(tmp_path: Path, variant: str) -> None:
    report_path = validate_capture_data(
        FIXTURE / "manifest.json",
        load_data_validation_config(CONFIG),
        tmp_path,
        validation_id=variant,
    )
    if variant == "quarantine_mismatch":
        quarantine_path = report_path.with_name("quarantine-manifest.json")
        quarantine = json.loads(quarantine_path.read_text())
        quarantine["validation_id"] = "other"
        quarantine_path.write_text(
            json.dumps(quarantine, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        quarantine_path.with_name("quarantine-manifest.sha256.json").write_text(
            json.dumps(
                {"sha256": hashlib.sha256(quarantine_path.read_bytes()).hexdigest()},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        def mutate(payload: dict[str, object]) -> None:
            if variant == "unsupported":
                payload["step"] = 12
            elif variant == "spec_changed":
                payload["research_specification_changed"] = True
            elif variant == "repaired":
                payload["missing_events_repaired"] = True
            elif variant == "source_unverified":
                payload["source_capture_verified"] = False
            elif variant == "days_invalid":
                payload["days"] = "bad"
            elif variant == "summary_mismatch":
                payload["summary"]["admitted_days"] = 1  # type: ignore[index]
            elif variant == "bad_admitted_day":
                payload["days"][0]["admission_status"] = "admitted"  # type: ignore[index]
                payload["days"][0]["reasons"] = ["still_bad"]  # type: ignore[index]
                payload["summary"]["admitted_days"] = 1  # type: ignore[index]
        _rewrite_validation_report(report_path, mutate)
    with pytest.raises(DataValidationVerificationError):
        verify_data_validation_report(report_path)


def test_report_invalid_json_is_rejected(tmp_path: Path) -> None:
    report = tmp_path / "validation-report.json"
    report.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataValidationVerificationError):
        verify_data_validation_report(report)


def test_low_level_validation_failure_paths(tmp_path: Path) -> None:
    from robust_execution.data_validation.models import ValidationIssue
    from robust_execution.data_validation.validator import (
        _load_snapshot,
        _positive_decimal,
        _validate_record_envelope,
    )

    with pytest.raises(ValueError, match="not a decimal"):
        _positive_decimal("not-a-number", "price")
    with pytest.raises(ValueError, match="finite and positive"):
        _positive_decimal("NaN", "price")

    bad_json = tmp_path / "bad.json.gz"
    with gzip.open(bad_json, "wt", encoding="utf-8") as handle:
        handle.write("not-json")
    with pytest.raises(DataValidationError, match="cannot read snapshot"):
        _load_snapshot(bad_json)

    not_object = tmp_path / "list.json.gz"
    with gzip.open(not_object, "wt", encoding="utf-8") as handle:
        json.dump([], handle)
    with pytest.raises(DataValidationError, match="not an object"):
        _load_snapshot(not_object)

    manifest = {"run_id": "run"}
    base: dict[str, object] = {
        "schema_version": 1,
        "run_id": "run",
        "connection_id": "connection-0000",
        "message_index": 0,
        "received_utc_ns": 1,
        "received_monotonic_ns": 1,
        "stream": "btcusdt@trade",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "raw_payload_utf8": "{}",
        "raw_payload_sha256": hashlib.sha256(b"{}").hexdigest(),
    }
    cases: list[dict[str, object]] = []
    missing = dict(base)
    del missing["stream"]
    cases.append(missing)
    provenance = dict(base, run_id="other")
    cases.append(provenance)
    negative = dict(base, message_index=-1)
    cases.append(negative)
    hash_bad = dict(base, raw_payload_sha256="0" * 64)
    cases.append(hash_bad)
    raw_bad = dict(base, raw_payload_utf8="not-json")
    raw_bad["raw_payload_sha256"] = hashlib.sha256(b"not-json").hexdigest()
    cases.append(raw_bad)
    wrapper_bad = dict(base, raw_payload_utf8="[]")
    wrapper_bad["raw_payload_sha256"] = hashlib.sha256(b"[]").hexdigest()
    cases.append(wrapper_bad)
    for record in cases:
        issues: list[ValidationIssue] = []
        assert _validate_record_envelope(record, manifest, issues) == (None, None)
        assert issues
