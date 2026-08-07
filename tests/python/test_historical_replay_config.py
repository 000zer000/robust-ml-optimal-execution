from __future__ import annotations

import json
from pathlib import Path

import pytest

from robust_execution.historical_replay.config import (
    HistoricalReplayConfigurationError,
    load_historical_replay_config,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/data/binance_historical_replay_sample.json"


def test_load_sample_config() -> None:
    config = load_historical_replay_config(CONFIG)
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.queue_position_semantics == "not_reconstructed_until_step16"
    assert config.top_levels == 10


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", 2),
        ("replay_id", ""),
        ("symbols", []),
        ("symbols", ["BTCUSDT", "BTCUSDT"]),
        ("symbols", ["btcusdt"]),
        ("observation_processing_delay_ns", -1),
        ("top_levels", 0),
        ("maximum_recent_trades", 0),
        ("checkpoint_policy", "fixed_grid"),
        ("queue_position_semantics", "exact_fifo"),
        ("market_impact_semantics", "endogenous"),
    ],
)
def test_reject_invalid_config(tmp_path: Path, field: str, value: object) -> None:
    data = json.loads(CONFIG.read_text())
    data[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(HistoricalReplayConfigurationError):
        load_historical_replay_config(path)


def test_research_config_requires_exact_snapshot_timestamp(tmp_path: Path) -> None:
    data = json.loads(CONFIG.read_text())
    data["require_research_admissible_input"] = True
    data["require_exact_snapshot_fetch_time_for_research"] = False
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(HistoricalReplayConfigurationError):
        load_historical_replay_config(path)


def test_reject_non_object_and_missing_field(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[]")
    with pytest.raises(HistoricalReplayConfigurationError):
        load_historical_replay_config(path)
    path.write_text("{}")
    with pytest.raises(HistoricalReplayConfigurationError):
        load_historical_replay_config(path)


def test_unreadable_and_invalid_json_config(tmp_path: Path) -> None:
    with pytest.raises(HistoricalReplayConfigurationError, match="cannot read"):
        load_historical_replay_config(tmp_path / "missing.json")
    path = tmp_path / "invalid.json"
    path.write_text("{")
    with pytest.raises(HistoricalReplayConfigurationError, match="cannot read"):
        load_historical_replay_config(path)
