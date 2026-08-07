"""Strict Step 13 raw-data validation configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class DataValidationConfigurationError(ValueError):
    """Raised when a Step 13 validation configuration is unsafe or ambiguous."""


@dataclass(frozen=True)
class AdmissionRules:
    require_live_origin: bool
    require_capture_complete: bool
    require_72h_pilot: bool
    require_whole_utc_day: bool
    boundary_tolerance_ns: int
    minimum_depth_messages_per_symbol: int
    minimum_trade_messages_per_symbol: int
    maximum_event_receive_delta_ns: int


@dataclass(frozen=True)
class DataValidationConfig:
    schema_version: int
    venue_id: str
    symbols: tuple[str, ...]
    allowed_data_origins: tuple[str, ...]
    primary_historical_study_repairs_missing_events: bool
    crossed_or_locked_books_allowed: bool
    negative_or_nonfinite_values_allowed: bool
    research_specification_changed: bool
    admission: AdmissionRules

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "venue_id": self.venue_id,
            "symbols": list(self.symbols),
            "allowed_data_origins": list(self.allowed_data_origins),
            "primary_historical_study_repairs_missing_events": self.primary_historical_study_repairs_missing_events,
            "crossed_or_locked_books_allowed": self.crossed_or_locked_books_allowed,
            "negative_or_nonfinite_values_allowed": self.negative_or_nonfinite_values_allowed,
            "research_specification_changed": self.research_specification_changed,
            "admission": {
                "require_live_origin": self.admission.require_live_origin,
                "require_capture_complete": self.admission.require_capture_complete,
                "require_72h_pilot": self.admission.require_72h_pilot,
                "require_whole_utc_day": self.admission.require_whole_utc_day,
                "boundary_tolerance_ns": self.admission.boundary_tolerance_ns,
                "minimum_depth_messages_per_symbol": self.admission.minimum_depth_messages_per_symbol,
                "minimum_trade_messages_per_symbol": self.admission.minimum_trade_messages_per_symbol,
                "maximum_event_receive_delta_ns": self.admission.maximum_event_receive_delta_ns,
            },
        }


def _require_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise DataValidationConfigurationError(f"{key} must be boolean")
    return value


def _require_int(obj: dict[str, Any], key: str, minimum: int) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise DataValidationConfigurationError(f"{key} must be an integer >= {minimum}")
    return value


def load_data_validation_config(path: Path) -> DataValidationConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationConfigurationError(f"cannot load data-validation config: {exc}") from exc
    if not isinstance(raw, dict):
        raise DataValidationConfigurationError("configuration root must be an object")
    if raw.get("schema_version") != 1:
        raise DataValidationConfigurationError("only schema_version 1 is supported")
    if raw.get("venue_id") != "binance_spot":
        raise DataValidationConfigurationError("venue_id must remain binance_spot")
    symbols = raw.get("symbols")
    if symbols != ["BTCUSDT", "ETHUSDT"]:
        raise DataValidationConfigurationError("symbols must be exactly BTCUSDT then ETHUSDT")
    origins = raw.get("allowed_data_origins")
    if origins != ["live_binance", "synthetic_transport_fixture"]:
        raise DataValidationConfigurationError("allowed_data_origins must preserve the Step 12 origins")
    admission = raw.get("admission")
    if not isinstance(admission, dict):
        raise DataValidationConfigurationError("admission must be an object")
    config = DataValidationConfig(
        schema_version=1,
        venue_id="binance_spot",
        symbols=("BTCUSDT", "ETHUSDT"),
        allowed_data_origins=("live_binance", "synthetic_transport_fixture"),
        primary_historical_study_repairs_missing_events=_require_bool(
            raw, "primary_historical_study_repairs_missing_events"
        ),
        crossed_or_locked_books_allowed=_require_bool(raw, "crossed_or_locked_books_allowed"),
        negative_or_nonfinite_values_allowed=_require_bool(
            raw, "negative_or_nonfinite_values_allowed"
        ),
        research_specification_changed=_require_bool(raw, "research_specification_changed"),
        admission=AdmissionRules(
            require_live_origin=_require_bool(admission, "require_live_origin"),
            require_capture_complete=_require_bool(admission, "require_capture_complete"),
            require_72h_pilot=_require_bool(admission, "require_72h_pilot"),
            require_whole_utc_day=_require_bool(admission, "require_whole_utc_day"),
            boundary_tolerance_ns=_require_int(admission, "boundary_tolerance_ns", 0),
            minimum_depth_messages_per_symbol=_require_int(
                admission, "minimum_depth_messages_per_symbol", 1
            ),
            minimum_trade_messages_per_symbol=_require_int(
                admission, "minimum_trade_messages_per_symbol", 1
            ),
            maximum_event_receive_delta_ns=_require_int(
                admission, "maximum_event_receive_delta_ns", 0
            ),
        ),
    )
    if config.primary_historical_study_repairs_missing_events:
        raise DataValidationConfigurationError("primary historical data may not be repaired")
    if config.crossed_or_locked_books_allowed:
        raise DataValidationConfigurationError("crossed or locked books may not be admitted")
    if config.negative_or_nonfinite_values_allowed:
        raise DataValidationConfigurationError("negative or non-finite market values may not be admitted")
    if config.research_specification_changed:
        raise DataValidationConfigurationError("Step 13 must not change the frozen specification")
    if not (
        config.admission.require_live_origin
        and config.admission.require_capture_complete
        and config.admission.require_72h_pilot
        and config.admission.require_whole_utc_day
    ):
        raise DataValidationConfigurationError("all primary admission safeguards must remain enabled")
    return config
