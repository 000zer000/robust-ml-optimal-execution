"""Strict configuration parsing for aggregate-L2 queue-model assumptions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class QueueModelConfigError(ValueError):
    """Raised when the Step 16 queue-model contract is invalid."""


@dataclass(frozen=True)
class QueueModelDefinition:
    model_id: str
    assumption: str
    additional_initial_ahead_bps: int
    fill_on_trade_through: bool


@dataclass(frozen=True)
class QueueModelContract:
    schema_version: str
    contract_id: str
    models: tuple[QueueModelDefinition, ...]
    sensitivity_additional_ahead_bps: tuple[int, ...]
    require_exact_synthetic_comparison: bool
    exact_fifo_reconstructed_historically: bool
    ghost_small_agent_assumption: bool


def _require_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    keys = set(value)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        raise QueueModelConfigError(f"{context} keys differ; missing={missing}, extra={extra}")


def load_queue_model_contract(path: Path) -> QueueModelContract:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise QueueModelConfigError("queue-model contract must be an object")
    _require_keys(
        raw,
        {
            "schema_version",
            "contract_id",
            "models",
            "sensitivity_additional_ahead_bps",
            "require_exact_synthetic_comparison",
            "exact_fifo_reconstructed_historically",
            "ghost_small_agent_assumption",
        },
        "queue-model contract",
    )
    if raw["schema_version"] != "queue-model-contract-v1":
        raise QueueModelConfigError("unsupported queue-model contract schema")
    if not isinstance(raw["contract_id"], str) or not raw["contract_id"]:
        raise QueueModelConfigError("contract_id must be non-empty")
    models_raw = raw["models"]
    if not isinstance(models_raw, list) or len(models_raw) != 3:
        raise QueueModelConfigError("exactly three queue models are required")
    models: list[QueueModelDefinition] = []
    for index, item in enumerate(models_raw):
        if not isinstance(item, dict):
            raise QueueModelConfigError(f"models[{index}] must be an object")
        _require_keys(
            item,
            {
                "model_id",
                "assumption",
                "additional_initial_ahead_bps",
                "fill_on_trade_through",
            },
            f"models[{index}]",
        )
        if item["assumption"] not in {"optimistic", "central", "pessimistic"}:
            raise QueueModelConfigError("unsupported queue assumption")
        if not isinstance(item["model_id"], str) or not item["model_id"]:
            raise QueueModelConfigError("model_id must be non-empty")
        ahead = item["additional_initial_ahead_bps"]
        if not isinstance(ahead, int) or isinstance(ahead, bool) or not 0 <= ahead <= 100_000:
            raise QueueModelConfigError("additional_initial_ahead_bps is invalid")
        if not isinstance(item["fill_on_trade_through"], bool):
            raise QueueModelConfigError("fill_on_trade_through must be boolean")
        models.append(
            QueueModelDefinition(
                model_id=item["model_id"],
                assumption=item["assumption"],
                additional_initial_ahead_bps=ahead,
                fill_on_trade_through=item["fill_on_trade_through"],
            )
        )
    if {model.assumption for model in models} != {"optimistic", "central", "pessimistic"}:
        raise QueueModelConfigError("models must include all three queue assumptions exactly once")
    sensitivity = raw["sensitivity_additional_ahead_bps"]
    if (
        not isinstance(sensitivity, list)
        or not sensitivity
        or any(not isinstance(value, int) or isinstance(value, bool) for value in sensitivity)
        or any(value < 0 or value > 100_000 for value in sensitivity)
        or sensitivity != sorted(set(sensitivity))
    ):
        raise QueueModelConfigError("sensitivity buffers must be sorted unique integers")
    for key in (
        "require_exact_synthetic_comparison",
        "exact_fifo_reconstructed_historically",
        "ghost_small_agent_assumption",
    ):
        if not isinstance(raw[key], bool):
            raise QueueModelConfigError(f"{key} must be boolean")
    if not raw["require_exact_synthetic_comparison"]:
        raise QueueModelConfigError("exact synthetic FIFO comparison cannot be disabled")
    if raw["exact_fifo_reconstructed_historically"]:
        raise QueueModelConfigError("historical exact FIFO reconstruction claim is forbidden")
    if not raw["ghost_small_agent_assumption"]:
        raise QueueModelConfigError("historical queue models require the ghost small-agent boundary")
    return QueueModelContract(
        schema_version=raw["schema_version"],
        contract_id=raw["contract_id"],
        models=tuple(models),
        sensitivity_additional_ahead_bps=tuple(sensitivity),
        require_exact_synthetic_comparison=raw["require_exact_synthetic_comparison"],
        exact_fifo_reconstructed_historically=raw["exact_fifo_reconstructed_historically"],
        ghost_small_agent_assumption=raw["ghost_small_agent_assumption"],
    )
