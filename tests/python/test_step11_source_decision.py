from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "data" / "market-data-source-decision-v1.schema.json"
DECISION_PATH = ROOT / "results" / "validation" / "step11" / "source_decision.json"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_step11_validation_script() -> None:
    path = ROOT / "scripts" / "validate_step11_source_decision.py"
    spec = importlib.util.spec_from_file_location("validate_step11_source_decision", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0


def test_step11_schema_and_decision() -> None:
    schema = _load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    decision = _load(DECISION_PATH)
    Draft202012Validator(schema).validate(decision)
    assert decision["research_specification_changed"] is False
    assert decision["paid_purchase_made"] is False
    assert decision["primary_venue"]["venue_id"] == "binance_spot"  # type: ignore[index]
    assert [item["symbol"] for item in decision["instruments"]] == [  # type: ignore[index]
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_step11_schema_rejects_unapproved_changes() -> None:
    schema = _load(SCHEMA_PATH)
    decision = _load(DECISION_PATH)
    validator = Draft202012Validator(schema)

    paid = copy.deepcopy(decision)
    paid["paid_purchase_made"] = True
    assert list(validator.iter_errors(paid))

    changed = copy.deepcopy(decision)
    changed["research_specification_changed"] = True
    assert list(validator.iter_errors(changed))

    wrong_venue = copy.deepcopy(decision)
    wrong_venue["primary_venue"]["venue_id"] = "coinbase"  # type: ignore[index]
    assert list(validator.iter_errors(wrong_venue))
