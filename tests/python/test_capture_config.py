from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_execution.data_capture.config import CaptureConfigurationError, load_capture_config


ROOT = Path(__file__).resolve().parents[2]


def test_load_capture_config_and_url() -> None:
    config = load_capture_config(ROOT / "configs/data/binance_capture_pilot.json")
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.pilot.required_duration_seconds == 259200
    assert config.pilot.rotate_before_seconds < 86400
    url = config.combined_stream_url()
    assert url.startswith("wss://data-stream.binance.vision/stream?streams=")
    assert "btcusdt@depth@100ms" in url
    assert "ethusdt@trade" in url
    assert url.endswith("timeUnit=MICROSECOND")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("venue_id",), "coinbase"),
        (("symbols",), ["BTCUSDT"]),
        (("timestamp_unit",), "MILLISECOND"),
        (("snapshot_limit",), 1000),
        (("research_specification_changed",), True),
        (("paid_data_required",), True),
        (("storage", "compression"), "zstd"),
        (("pilot", "required_duration_seconds"), 3600),
        (("pilot", "rotate_before_seconds"), 86400),
    ],
)
def test_invalid_capture_config_is_rejected(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    payload = json.loads((ROOT / "configs/data/binance_capture_pilot.json").read_text())
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    config_path = tmp_path / "bad.json"
    config_path.write_text(json.dumps(payload))
    with pytest.raises(CaptureConfigurationError):
        load_capture_config(config_path)
