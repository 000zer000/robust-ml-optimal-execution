from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_execution.canonical_data.config import (
    CanonicalDataConfigurationError,
    load_canonical_data_config,
)

CONFIG = Path("configs/data/binance_canonical_sample.json")


def test_load_canonical_config() -> None:
    config = load_canonical_data_config(CONFIG)
    assert config.output_tier == "sample"
    assert config.instrument("BTCUSDT").price_increment == "0.01"
    assert config.to_dict()["research_specification_changed"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("venue_id",), "other"),
        (("symbols",), ["BTCUSDT"]),
        (("input_policy", "repair_or_interpolate_missing_events"), True),
        (("format_policy", "base_format"), "csv"),
        (("format_policy", "parquet_required_for_processed"), False),
        (("research_specification_changed",), True),
        (("instruments", 0, "price_increment"), "0"),
    ],
)
def test_reject_weakened_config(tmp_path: Path, path: tuple[object, ...], value: object) -> None:
    raw = json.loads(CONFIG.read_text())
    target: object = raw
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    candidate = tmp_path / "config.json"
    candidate.write_text(json.dumps(raw))
    with pytest.raises(CanonicalDataConfigurationError):
        load_canonical_data_config(candidate)


def test_missing_instrument_raises() -> None:
    config = load_canonical_data_config(CONFIG)
    with pytest.raises(CanonicalDataConfigurationError):
        config.instrument("SOLUSDT")
