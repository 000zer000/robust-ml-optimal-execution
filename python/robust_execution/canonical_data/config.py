"""Strict Step 14 canonical-data configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class CanonicalDataConfigurationError(ValueError):
    """Raised when canonicalisation settings weaken provenance or exactness."""


@dataclass(frozen=True)
class InstrumentScale:
    symbol: str
    price_increment: str
    quantity_increment: str
    source: str

    @property
    def price_decimal(self) -> Decimal:
        return Decimal(self.price_increment)

    @property
    def quantity_decimal(self) -> Decimal:
        return Decimal(self.quantity_increment)


@dataclass(frozen=True)
class InputPolicy:
    require_verified_capture: bool
    require_structurally_valid_day: bool
    reject_quarantined_days: bool
    require_research_admission_for_processed: bool
    allow_structurally_valid_fixture_sample: bool
    repair_or_interpolate_missing_events: bool


@dataclass(frozen=True)
class FormatPolicy:
    base_format: str
    compression: str
    exact_decimal_conversion: bool
    parquet_required_for_processed: bool
    parquet_optional_for_sample: bool


@dataclass(frozen=True)
class CanonicalDataConfig:
    schema_version: int
    venue_id: str
    symbols: tuple[str, ...]
    output_tier: str
    input_policy: InputPolicy
    format_policy: FormatPolicy
    instruments: tuple[InstrumentScale, ...]
    research_specification_changed: bool

    def instrument(self, symbol: str) -> InstrumentScale:
        for item in self.instruments:
            if item.symbol == symbol:
                return item
        raise CanonicalDataConfigurationError(f"missing instrument scale for {symbol}")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "venue_id": self.venue_id,
            "symbols": list(self.symbols),
            "output_tier": self.output_tier,
            "input_policy": asdict(self.input_policy),
            "format_policy": asdict(self.format_policy),
            "instruments": [asdict(item) for item in self.instruments],
            "research_specification_changed": self.research_specification_changed,
        }


def _require_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise CanonicalDataConfigurationError(f"{key} must be boolean")
    return value


def _positive_increment(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise CanonicalDataConfigurationError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise CanonicalDataConfigurationError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise CanonicalDataConfigurationError(f"{field} must be finite and positive")
    normalized = parsed.normalize().as_tuple()
    if (
        normalized.digits == (1,)
        and isinstance(normalized.exponent, int)
        and normalized.exponent > 0
    ):
        raise CanonicalDataConfigurationError(f"{field} increment is too coarse")
    return value


def load_canonical_data_config(path: Path) -> CanonicalDataConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalDataConfigurationError(f"cannot load canonical-data config: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise CanonicalDataConfigurationError("only schema_version 1 is supported")
    if raw.get("venue_id") != "binance_spot":
        raise CanonicalDataConfigurationError("venue_id must remain binance_spot")
    if raw.get("symbols") != ["BTCUSDT", "ETHUSDT"]:
        raise CanonicalDataConfigurationError("symbols must be exactly BTCUSDT then ETHUSDT")
    tier = raw.get("output_tier")
    if tier not in {"sample", "processed"}:
        raise CanonicalDataConfigurationError("output_tier must be sample or processed")
    input_raw = raw.get("input_policy")
    format_raw = raw.get("format_policy")
    instruments_raw = raw.get("instruments")
    if not isinstance(input_raw, dict) or not isinstance(format_raw, dict):
        raise CanonicalDataConfigurationError("input_policy and format_policy must be objects")
    if not isinstance(instruments_raw, list) or len(instruments_raw) != 2:
        raise CanonicalDataConfigurationError("instruments must contain exactly two definitions")
    instruments: list[InstrumentScale] = []
    for expected, item in zip(("BTCUSDT", "ETHUSDT"), instruments_raw, strict=True):
        if not isinstance(item, dict) or item.get("symbol") != expected:
            raise CanonicalDataConfigurationError("instrument order must match symbols")
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise CanonicalDataConfigurationError("instrument source must be non-empty")
        instruments.append(
            InstrumentScale(
                symbol=expected,
                price_increment=_positive_increment(item.get("price_increment"), "price_increment"),
                quantity_increment=_positive_increment(
                    item.get("quantity_increment"), "quantity_increment"
                ),
                source=source,
            )
        )
    config = CanonicalDataConfig(
        schema_version=1,
        venue_id="binance_spot",
        symbols=("BTCUSDT", "ETHUSDT"),
        output_tier=tier,
        input_policy=InputPolicy(
            require_verified_capture=_require_bool(input_raw, "require_verified_capture"),
            require_structurally_valid_day=_require_bool(
                input_raw, "require_structurally_valid_day"
            ),
            reject_quarantined_days=_require_bool(input_raw, "reject_quarantined_days"),
            require_research_admission_for_processed=_require_bool(
                input_raw, "require_research_admission_for_processed"
            ),
            allow_structurally_valid_fixture_sample=_require_bool(
                input_raw, "allow_structurally_valid_fixture_sample"
            ),
            repair_or_interpolate_missing_events=_require_bool(
                input_raw, "repair_or_interpolate_missing_events"
            ),
        ),
        format_policy=FormatPolicy(
            base_format=str(format_raw.get("base_format", "")),
            compression=str(format_raw.get("compression", "")),
            exact_decimal_conversion=_require_bool(format_raw, "exact_decimal_conversion"),
            parquet_required_for_processed=_require_bool(
                format_raw, "parquet_required_for_processed"
            ),
            parquet_optional_for_sample=_require_bool(format_raw, "parquet_optional_for_sample"),
        ),
        instruments=tuple(instruments),
        research_specification_changed=_require_bool(raw, "research_specification_changed"),
    )
    if config.research_specification_changed:
        raise CanonicalDataConfigurationError("Step 14 must not change the frozen specification")
    if not (
        config.input_policy.require_verified_capture
        and config.input_policy.require_structurally_valid_day
        and config.input_policy.reject_quarantined_days
        and config.input_policy.require_research_admission_for_processed
    ):
        raise CanonicalDataConfigurationError("canonical input safeguards must remain enabled")
    if config.input_policy.repair_or_interpolate_missing_events:
        raise CanonicalDataConfigurationError("missing events may not be repaired or interpolated")
    if config.format_policy.base_format != "re_columnar_v1":
        raise CanonicalDataConfigurationError("base_format must remain re_columnar_v1")
    if config.format_policy.compression != "gzip":
        raise CanonicalDataConfigurationError("compression must remain gzip")
    if not config.format_policy.exact_decimal_conversion:
        raise CanonicalDataConfigurationError("decimal conversion must remain exact")
    if not config.format_policy.parquet_required_for_processed:
        raise CanonicalDataConfigurationError("Parquet must remain mandatory for processed data")
    if not config.format_policy.parquet_optional_for_sample:
        raise CanonicalDataConfigurationError("sample Parquet policy must remain explicit")
    return config
