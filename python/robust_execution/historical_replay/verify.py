"""Independent verification of Step 15 historical replay artifacts."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


class HistoricalReplayVerificationError(RuntimeError):
    pass


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalReplayVerificationError(f"cannot read {path}: {exc}") from exc


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _table(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    schema_path = root / str(item.get("schema_relative_path"))
    data_path = root / str(item.get("data_relative_path"))
    if _digest(schema_path) != item.get("schema_sha256") or _digest(data_path) != item.get(
        "data_sha256"
    ):
        raise HistoricalReplayVerificationError("replay table digest mismatch")
    try:
        with gzip.open(data_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalReplayVerificationError(f"cannot read replay table: {exc}") from exc
    if payload.get("row_count") != item.get("row_count"):
        raise HistoricalReplayVerificationError("replay table row count mismatch")
    return payload


def verify_historical_replay(manifest_path: Path) -> dict[str, object]:
    manifest = _json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("step") != 15:
        raise HistoricalReplayVerificationError("unsupported Step 15 manifest")
    if manifest.get("research_specification_changed") is not False:
        raise HistoricalReplayVerificationError("replay claims a specification change")
    if manifest.get("exact_fifo_reconstructed") is not False:
        raise HistoricalReplayVerificationError("aggregate L2 replay cannot claim exact FIFO")
    if manifest.get("endogenous_impact_modelled") is not False:
        raise HistoricalReplayVerificationError("historical replay cannot claim endogenous impact")
    if manifest.get("queue_position_semantics") != "not_reconstructed_until_step16":
        raise HistoricalReplayVerificationError("queue-position boundary was weakened")
    expected = _json(manifest_path.with_name("replay-manifest.sha256.json"))
    actual = _digest(manifest_path)
    if expected != {"sha256": actual}:
        raise HistoricalReplayVerificationError("replay manifest digest mismatch")
    tables = manifest.get("tables")
    if not isinstance(tables, list) or len(tables) != 3:
        raise HistoricalReplayVerificationError("exactly three Step 15 tables are required")
    loaded: dict[str, dict[str, Any]] = {}
    root = manifest_path.parent
    for item in tables:
        if not isinstance(item, dict):
            raise HistoricalReplayVerificationError("replay table entry must be an object")
        name = str(item.get("table_name"))
        if name in loaded:
            raise HistoricalReplayVerificationError("duplicate replay table name")
        loaded[name] = _table(root, item)
    if set(loaded) != {"replay_events", "replay_observations", "connection_integrity"}:
        raise HistoricalReplayVerificationError("unexpected Step 15 table set")
    events = loaded["replay_events"]["columns"]
    observations = loaded["replay_observations"]["columns"]
    event_rows = int(loaded["replay_events"]["row_count"])
    observation_rows = int(loaded["replay_observations"]["row_count"])
    if event_rows != manifest.get("event_count") or observation_rows != manifest.get(
        "observation_count"
    ):
        raise HistoricalReplayVerificationError("manifest event/observation counts differ")
    prior_keys: dict[str, tuple[int, int, int]] = {}
    priorities = {"snapshot": 0, "depth_batch": 1, "trade": 2}
    for index in range(event_rows):
        event_time = int(events["event_time_ns"][index])
        receive_time = int(events["receive_time_ns"][index])
        available_time = int(events["available_time_ns"][index])
        if not event_time <= receive_time <= available_time:
            raise HistoricalReplayVerificationError("replay event violates causal timestamps")
        kind = str(events["event_kind"][index])
        key = (
            available_time,
            priorities.get(kind, 99),
            int(events["canonical_message_sequence"][index]),
        )
        symbol = str(events["symbol"][index])
        prior_key = prior_keys.get(symbol)
        if prior_key is not None and key < prior_key:
            raise HistoricalReplayVerificationError("replay events are not deterministically ordered")
        prior_keys[symbol] = key
    for index in range(observation_rows):
        decision = int(observations["decision_time_ns"][index])
        maximum_event = int(observations["maximum_event_time_ns"][index])
        maximum_available = int(observations["maximum_available_time_ns"][index])
        if maximum_event > maximum_available or maximum_available > decision:
            raise HistoricalReplayVerificationError("observation contains unavailable information")
        if int(observations["best_bid_ticks"][index]) >= int(
            observations["best_ask_ticks"][index]
        ):
            raise HistoricalReplayVerificationError("observation book is locked or crossed")
    if manifest.get("source_dataset_classification") == "sample_only_non_research" and manifest.get(
        "research_admissible"
    ) is not False:
        raise HistoricalReplayVerificationError("sample replay cannot be research admissible")
    return {
        "status": "ok",
        "replay_id": manifest.get("replay_id"),
        "events": event_rows,
        "observations": observation_rows,
        "connections": manifest.get("connection_count"),
        "manifest_sha256": actual,
        "research_admissible": manifest.get("research_admissible"),
    }
