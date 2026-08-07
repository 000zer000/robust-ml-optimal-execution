"""Strict Step 15 historical replay configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class HistoricalReplayConfigurationError(ValueError):
    """Raised when a replay configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class HistoricalReplayConfig:
    schema_version: int
    replay_id: str
    symbols: tuple[str, ...]
    observation_processing_delay_ns: int
    top_levels: int
    maximum_recent_trades: int
    checkpoint_policy: str
    require_research_admissible_input: bool
    allow_connection_start_proxy_for_sample: bool
    require_exact_snapshot_fetch_time_for_research: bool
    queue_position_semantics: str
    market_impact_semantics: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "replay_id": self.replay_id,
            "symbols": list(self.symbols),
            "observation_processing_delay_ns": self.observation_processing_delay_ns,
            "top_levels": self.top_levels,
            "maximum_recent_trades": self.maximum_recent_trades,
            "checkpoint_policy": self.checkpoint_policy,
            "require_research_admissible_input": self.require_research_admissible_input,
            "allow_connection_start_proxy_for_sample": self.allow_connection_start_proxy_for_sample,
            "require_exact_snapshot_fetch_time_for_research": (
                self.require_exact_snapshot_fetch_time_for_research
            ),
            "queue_position_semantics": self.queue_position_semantics,
            "market_impact_semantics": self.market_impact_semantics,
        }


def _required(data: dict[str, Any], name: str, expected: type[Any]) -> Any:
    value = data.get(name)
    if not isinstance(value, expected):
        raise HistoricalReplayConfigurationError(f"{name} must be {expected.__name__}")
    return value


def load_historical_replay_config(path: Path) -> HistoricalReplayConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalReplayConfigurationError(f"cannot read replay config: {exc}") from exc
    if not isinstance(data, dict):
        raise HistoricalReplayConfigurationError("replay config must be an object")
    symbols_raw = _required(data, "symbols", list)
    symbols = tuple(str(item) for item in symbols_raw)
    config = HistoricalReplayConfig(
        schema_version=int(_required(data, "schema_version", int)),
        replay_id=str(_required(data, "replay_id", str)),
        symbols=symbols,
        observation_processing_delay_ns=int(
            _required(data, "observation_processing_delay_ns", int)
        ),
        top_levels=int(_required(data, "top_levels", int)),
        maximum_recent_trades=int(_required(data, "maximum_recent_trades", int)),
        checkpoint_policy=str(_required(data, "checkpoint_policy", str)),
        require_research_admissible_input=bool(
            _required(data, "require_research_admissible_input", bool)
        ),
        allow_connection_start_proxy_for_sample=bool(
            _required(data, "allow_connection_start_proxy_for_sample", bool)
        ),
        require_exact_snapshot_fetch_time_for_research=bool(
            _required(data, "require_exact_snapshot_fetch_time_for_research", bool)
        ),
        queue_position_semantics=str(_required(data, "queue_position_semantics", str)),
        market_impact_semantics=str(_required(data, "market_impact_semantics", str)),
    )
    if config.schema_version != 1 or not config.replay_id:
        raise HistoricalReplayConfigurationError("unsupported schema or empty replay_id")
    if len(config.symbols) < 1 or len(set(config.symbols)) != len(config.symbols):
        raise HistoricalReplayConfigurationError("symbols must be non-empty and unique")
    if any(not symbol or symbol != symbol.upper() for symbol in config.symbols):
        raise HistoricalReplayConfigurationError("symbols must be non-empty uppercase strings")
    if config.observation_processing_delay_ns < 0:
        raise HistoricalReplayConfigurationError("processing delay cannot be negative")
    if config.top_levels < 1 or config.maximum_recent_trades < 1:
        raise HistoricalReplayConfigurationError("observation limits must be positive")
    if config.checkpoint_policy != "after_each_delivered_event_validation_only":
        raise HistoricalReplayConfigurationError("unsupported Step 15 checkpoint policy")
    if config.queue_position_semantics != "not_reconstructed_until_step16":
        raise HistoricalReplayConfigurationError("Step 15 cannot claim queue reconstruction")
    if config.market_impact_semantics != "ghost_small_agent_no_endogenous_impact":
        raise HistoricalReplayConfigurationError("historical replay cannot claim endogenous impact")
    if config.require_research_admissible_input and not config.require_exact_snapshot_fetch_time_for_research:
        raise HistoricalReplayConfigurationError(
            "research replay must require exact snapshot fetch timestamps"
        )
    return config
