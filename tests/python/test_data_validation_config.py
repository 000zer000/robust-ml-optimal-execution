from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_execution.data_validation.config import (
    DataValidationConfigurationError,
    load_data_validation_config,
)

ROOT = Path(__file__).resolve().parents[2]


def test_load_step13_validation_config() -> None:
    config = load_data_validation_config(ROOT / "configs/data/binance_raw_validation.json")
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.admission.require_72h_pilot is True
    assert config.primary_historical_study_repairs_missing_events is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("research_specification_changed",), True),
        (("primary_historical_study_repairs_missing_events",), True),
        (("crossed_or_locked_books_allowed",), True),
        (("negative_or_nonfinite_values_allowed",), True),
        (("admission", "require_live_origin"), False),
        (("admission", "require_capture_complete"), False),
        (("admission", "require_72h_pilot"), False),
        (("admission", "require_whole_utc_day"), False),
    ],
)
def test_validation_config_rejects_weakened_safeguards(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    payload = json.loads((ROOT / "configs/data/binance_raw_validation.json").read_text())
    cursor = payload
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationConfigurationError):
        load_data_validation_config(target)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema_version": 2},
        {"schema_version": 1, "venue_id": "other"},
        {"schema_version": 1, "venue_id": "binance_spot", "symbols": []},
        {
            "schema_version": 1,
            "venue_id": "binance_spot",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "allowed_data_origins": [],
        },
        {
            "schema_version": 1,
            "venue_id": "binance_spot",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "allowed_data_origins": ["live_binance", "synthetic_transport_fixture"],
            "admission": [],
        },
    ],
)
def test_validation_config_rejects_malformed_roots(tmp_path: Path, payload: object) -> None:
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationConfigurationError):
        load_data_validation_config(target)


def test_validation_config_rejects_unreadable_and_invalid_numbers(tmp_path: Path) -> None:
    with pytest.raises(DataValidationConfigurationError):
        load_data_validation_config(tmp_path / "missing.json")
    payload = json.loads((ROOT / "configs/data/binance_raw_validation.json").read_text())
    payload["admission"]["boundary_tolerance_ns"] = -1
    target = tmp_path / "bad-number.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationConfigurationError):
        load_data_validation_config(target)


def test_validation_config_requires_boolean_type(tmp_path: Path) -> None:
    payload = json.loads((ROOT / "configs/data/binance_raw_validation.json").read_text())
    payload["research_specification_changed"] = 0
    target = tmp_path / "bad-bool.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationConfigurationError):
        load_data_validation_config(target)
