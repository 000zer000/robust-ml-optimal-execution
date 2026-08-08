#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "data" / "market-data-source-decision-v1.schema.json"
DECISION_PATH = ROOT / "results" / "validation" / "step11" / "source_decision.json"
CONFIG_PATH = ROOT / "configs" / "data" / "binance_spot_primary.json"
SAMPLE_PATH = ROOT / "data" / "sample" / "source_selection" / "source_decision.json"
HASH_PATH = ROOT / "results" / "validation" / "step11" / "source_decision.json.sha256"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _assert_rejected(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    if not list(validator.iter_errors(value)):
        raise RuntimeError(f"negative schema control unexpectedly passed: {label}")


def main() -> int:
    schema = _load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    decision = _load(DECISION_PATH)
    validator.validate(decision)

    _require(CONFIG_PATH.read_bytes() == DECISION_PATH.read_bytes(), "config differs from decision")
    _require(SAMPLE_PATH.read_bytes() == DECISION_PATH.read_bytes(), "sample differs from decision")

    _require(decision["research_specification_changed"] is False, "Step 11 changed specification")
    _require(decision["paid_purchase_made"] is False, "paid purchase recorded without approval")
    _require(decision["primary_venue"]["venue_id"] == "binance_spot", "wrong venue")
    _require(
        [item["symbol"] for item in decision["instruments"]] == ["BTCUSDT", "ETHUSDT"],
        "wrong or reordered instrument set",
    )

    contract = decision["live_feed_contract"]
    expected_contract = {
        "depth_stream_template": "<symbol_lower>@depth@100ms",
        "trade_stream_template": "<symbol_lower>@trade",
        "first_update_id_field": "U",
        "final_update_id_field": "u",
        "depth_snapshot_limit_per_side": 5000,
        "connection_rotation_required_before_hours": 24,
        "timestamp_unit_parameter": "timeUnit=MICROSECOND",
        "gap_policy": "invalidate_current_book_and_rebuild_from_new_snapshot",
    }
    for key, expected in expected_contract.items():
        _require(contract.get(key) == expected, f"unexpected live-feed contract field {key}")

    sources = decision["historical_sources"]
    _require(
        sources["canonical_raw_corpus"]["source"]
        == "self_capture_from_official_binance_market_data_only_endpoints",
        "official self-capture is not canonical",
    )
    _require(
        sources["canonical_raw_corpus"]["minimum_valid_whole_days_per_instrument"] == 100,
        "minimum whole-day requirement changed",
    )
    _require(
        sources["accelerated_backfill"]["status"]
        == "conditionally_selected_pending_user_purchase_approval",
        "Tardis access is not approval-gated",
    )

    publication = decision["publication_policy"]
    _require(publication["commit_credentials"] is False, "credentials may not be committed")
    _require(publication["commit_raw_market_data"] is False, "raw market data may not be committed")
    _require(
        publication["written_license_clearance_required_before_any_market_data_release"] is True,
        "written licence clearance is not required",
    )

    required_domains = {
        "github.com",
        "docs.tardis.dev",
        "bybit-exchange.github.io",
        "docs.cdp.coinbase.com",
    }
    actual_domains = {
        url.split("/", 3)[2]
        for url in decision["source_urls"].values()
        if url.startswith("https://")
    }
    _require(
        required_domains.issubset(actual_domains), "required primary-source domains are missing"
    )

    paid = copy.deepcopy(decision)
    paid["paid_purchase_made"] = True
    _assert_rejected(validator, paid, "paid purchase")

    wrong_venue = copy.deepcopy(decision)
    wrong_venue["primary_venue"]["venue_id"] = "other"
    _assert_rejected(validator, wrong_venue, "wrong venue")

    one_instrument = copy.deepcopy(decision)
    one_instrument["instruments"] = one_instrument["instruments"][:1]
    _assert_rejected(validator, one_instrument, "one instrument")

    changed_scope = copy.deepcopy(decision)
    changed_scope["research_specification_changed"] = True
    _assert_rejected(validator, changed_scope, "scope change")

    digest = _sha256(DECISION_PATH)
    expected_digest = HASH_PATH.read_text(encoding="utf-8").split()[0]
    _require(digest == expected_digest, "Step 11 decision hash mismatch")
    print(
        "Step 11 source decision: PASS "
        f"(Binance Spot, BTCUSDT/ETHUSDT, no purchase, sha256={digest[:12]}...)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
