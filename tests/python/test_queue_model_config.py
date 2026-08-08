from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from robust_execution.queue_models.config import QueueModelConfigError, load_queue_model_contract

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/data/aggregate_queue_models.json"


def test_load_queue_model_contract() -> None:
    contract = load_queue_model_contract(CONFIG)
    assert contract.contract_id == "step16-aggregate-l2-queue-v1"
    assert [model.assumption for model in contract.models] == [
        "optimistic",
        "central",
        "pessimistic",
    ]
    assert contract.sensitivity_additional_ahead_bps == (0, 2500, 5000)
    assert contract.require_exact_synthetic_comparison
    assert not contract.exact_fifo_reconstructed_historically
    assert contract.ghost_small_agent_assumption


def write_config(tmp_path: Path, mutation: Callable[[dict[str, Any]], None]) -> Path:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    mutation(value)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schema_version="wrong"),
        lambda value: value.pop("contract_id"),
        lambda value: value.update(extra=True),
        lambda value: value.update(models=[]),
        lambda value: value["models"][0].update(assumption="unknown"),
        lambda value: value["models"][0].update(model_id=""),
        lambda value: value["models"][0].update(additional_initial_ahead_bps=-1),
        lambda value: value["models"][0].update(additional_initial_ahead_bps=True),
        lambda value: value["models"][0].update(fill_on_trade_through="yes"),
        lambda value: value["models"][0].update(extra=True),
        lambda value: value.update(sensitivity_additional_ahead_bps=[2500, 0]),
        lambda value: value.update(sensitivity_additional_ahead_bps=[0, 0]),
        lambda value: value.update(require_exact_synthetic_comparison=False),
        lambda value: value.update(exact_fifo_reconstructed_historically=True),
        lambda value: value.update(ghost_small_agent_assumption=False),
    ],
)
def test_invalid_queue_model_contracts(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    with pytest.raises(QueueModelConfigError):
        load_queue_model_contract(write_config(tmp_path, mutation))
