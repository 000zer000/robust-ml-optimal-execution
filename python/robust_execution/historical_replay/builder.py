"""Build immutable Step 15 aggregate-L2 replay events and causal observations."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from robust_execution import __version__
from robust_execution.canonical_data.models import write_columnar_table
from robust_execution.canonical_data.verify import verify_canonical_dataset
from robust_execution.data_capture.models import canonical_json_bytes
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.historical_replay.config import HistoricalReplayConfig
from robust_execution.historical_replay.tables import HistoricalTableError, read_table


class HistoricalReplayError(RuntimeError):
    """Raised when canonical data cannot be replayed without ambiguity."""


def _sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _tables(manifest: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in manifest.get("tables", []):
        if isinstance(item, dict):
            result[str(item.get("table_name"))] = str(item.get("data_relative_path"))
    required = {"source_records", "book_snapshots", "book_deltas", "trades"}
    if not required.issubset(result):
        raise HistoricalReplayError("canonical dataset lacks replay tables")
    return result


def _schemas() -> dict[str, tuple[tuple[str, ...], dict[str, object]]]:
    definitions: dict[str, tuple[tuple[str, ...], dict[str, object]]] = {}

    def add(name: str, columns: tuple[tuple[str, str], ...]) -> None:
        order = tuple(column for column, _ in columns)
        definitions[name] = (
            order,
            {
                "schema_version": 1,
                "table_name": name,
                "columns": [
                    {"name": column, "logical_type": logical, "nullable": False}
                    for column, logical in columns
                ],
            },
        )

    add(
        "replay_events",
        (
            ("replay_event_index", "int64"),
            ("symbol", "utf8"),
            ("connection_id", "utf8"),
            ("event_kind", "enum:snapshot|depth_batch|trade"),
            ("event_time_ns", "timestamp_ns_utc"),
            ("receive_time_ns", "timestamp_ns_utc"),
            ("available_time_ns", "timestamp_ns_utc"),
            ("canonical_message_sequence", "int64"),
            ("source_sequence_start", "int64"),
            ("source_sequence_end", "int64"),
            ("row_count", "int64"),
            ("payload_sha256", "sha256_hex"),
            ("snapshot_timestamp_semantics", "utf8"),
        ),
    )
    add(
        "replay_observations",
        (
            ("observation_index", "int64"),
            ("symbol", "utf8"),
            ("decision_time_ns", "timestamp_ns_utc"),
            ("maximum_event_time_ns", "timestamp_ns_utc"),
            ("maximum_available_time_ns", "timestamp_ns_utc"),
            ("delivered_event_count", "int64"),
            ("best_bid_ticks", "int64"),
            ("best_ask_ticks", "int64"),
            ("visible_bid_lots", "int64"),
            ("visible_ask_lots", "int64"),
            ("recent_trade_count", "int64"),
            ("book_state_sha256", "sha256_hex"),
            ("lineage_sha256", "sha256_hex"),
        ),
    )
    add(
        "connection_integrity",
        (
            ("symbol", "utf8"),
            ("connection_id", "utf8"),
            ("snapshot_last_update_id", "int64"),
            ("bridging_first_update_id", "int64"),
            ("bridging_final_update_id", "int64"),
            ("depth_batch_count", "int64"),
            ("trade_count", "int64"),
            ("sequence_gap_count", "int64"),
            ("crossed_book_count", "int64"),
            ("synchronized", "bool"),
            ("snapshot_timestamp_semantics", "utf8"),
        ),
    )
    return definitions


def _top(book: dict[int, int], count: int, reverse: bool) -> list[tuple[int, int]]:
    return sorted(book.items(), reverse=reverse)[:count]


def _book_hash(bids: dict[int, int], asks: dict[int, int]) -> str:
    return _sha256_json({"bids": sorted(bids.items(), reverse=True), "asks": sorted(asks.items())})


def _materialize_symbol_events(
    staged_events: list[dict[str, Any]],
    config: HistoricalReplayConfig,
    symbol: str,
    event_index: int,
    observation_index: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    event_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    bids: dict[int, int] = {}
    asks: dict[int, int] = {}
    recent: deque[dict[str, Any]] = deque(maxlen=config.maximum_recent_trades)
    synchronized = False
    delivered = 0
    maximum_event_time = 0
    maximum_available_time = 0

    for staged in staged_events:
        event = dict(staged)
        kind = str(event["event_kind"])
        payload = event.pop("payload")
        event.pop("priority")
        if kind == "connection_reset":
            bids.clear()
            asks.clear()
            recent.clear()
            synchronized = False
            continue
        event["replay_event_index"] = event_index
        event["payload_sha256"] = _sha256_json(payload)
        event_index += 1
        if int(event["event_time_ns"]) > int(event["receive_time_ns"]) or int(
            event["receive_time_ns"]
        ) > int(event["available_time_ns"]):
            raise HistoricalReplayError("replay event violates causal timestamp order")
        if kind == "snapshot":
            bids = {int(price): int(quantity) for price, quantity in payload["bids"]}
            asks = {int(price): int(quantity) for price, quantity in payload["asks"]}
            synchronized = False
        elif kind == "depth_batch":
            for update in payload:
                book = bids if update["side"] == "bid" else asks
                price = int(update["price_ticks"])
                quantity = int(update["quantity_lots"])
                if bool(update["is_delete"]):
                    book.pop(price, None)
                else:
                    book[price] = quantity
            synchronized = True
        elif kind == "trade":
            recent.append(payload)
        else:
            raise HistoricalReplayError("unsupported staged replay event")
        delivered += 1
        maximum_event_time = max(maximum_event_time, int(event["event_time_ns"]))
        maximum_available_time = max(maximum_available_time, int(event["available_time_ns"]))
        event_rows.append(event)
        if not synchronized:
            continue
        top_bids = _top(bids, config.top_levels, True)
        top_asks = _top(asks, config.top_levels, False)
        if not top_bids or not top_asks or top_bids[0][0] >= top_asks[0][0]:
            raise HistoricalReplayError(
                "reconstructed historical book is empty, locked, or crossed"
            )
        lineage = {
            "symbol": symbol,
            "delivered_event_count": delivered,
            "maximum_event_time_ns": maximum_event_time,
            "maximum_available_time_ns": maximum_available_time,
            "last_replay_event_index": int(event["replay_event_index"]),
        }
        observation_rows.append(
            {
                "observation_index": observation_index,
                "symbol": symbol,
                "decision_time_ns": int(event["available_time_ns"]),
                "maximum_event_time_ns": maximum_event_time,
                "maximum_available_time_ns": maximum_available_time,
                "delivered_event_count": delivered,
                "best_bid_ticks": top_bids[0][0],
                "best_ask_ticks": top_asks[0][0],
                "visible_bid_lots": sum(quantity for _, quantity in top_bids),
                "visible_ask_lots": sum(quantity for _, quantity in top_asks),
                "recent_trade_count": len(recent),
                "book_state_sha256": _book_hash(bids, asks),
                "lineage_sha256": _sha256_json(lineage),
            }
        )
        observation_index += 1
    return event_rows, observation_rows, event_index, observation_index


def build_historical_replay(
    canonical_manifest_path: Path,
    config: HistoricalReplayConfig,
    output_root: Path,
    replay_id: str | None = None,
) -> Path:
    verification = verify_canonical_dataset(canonical_manifest_path)
    manifest = json.loads(canonical_manifest_path.read_text(encoding="utf-8"))
    if config.require_research_admissible_input and not bool(manifest.get("research_admissible")):
        raise HistoricalReplayError(
            "research replay requires a research-admissible canonical input"
        )
    if tuple(manifest.get("symbols", [])) != config.symbols:
        raise HistoricalReplayError("replay symbols must exactly match canonical symbols and order")
    classification = str(manifest.get("dataset_classification"))
    sample = classification == "sample_only_non_research"
    if sample and not config.allow_connection_start_proxy_for_sample:
        raise HistoricalReplayError("sample replay requires explicit snapshot proxy permission")
    if not sample and config.require_exact_snapshot_fetch_time_for_research:
        raise HistoricalReplayError(
            "Step 14 lacks exact snapshot fetch timestamps; research replay is blocked"
        )
    identifier = replay_id or config.replay_id
    if not identifier:
        raise HistoricalReplayError("replay_id cannot be empty")
    target = output_root / identifier
    if target.exists():
        raise HistoricalReplayError(f"replay output already exists: {target}")

    table_paths = _tables(manifest)
    root = canonical_manifest_path.parent
    try:
        source = read_table(root, table_paths["source_records"])
        snapshots = read_table(root, table_paths["book_snapshots"])
        deltas = read_table(root, table_paths["book_deltas"])
        trades = read_table(root, table_paths["trades"])
    except HistoricalTableError as exc:
        raise HistoricalReplayError(str(exc)) from exc

    source_by_sequence = {int(row["canonical_message_sequence"]): row for row in source}
    delta_by_sequence: dict[int, list[dict[str, Any]]] = defaultdict(list)
    trade_by_sequence: dict[int, dict[str, Any]] = {}
    for row in deltas:
        delta_by_sequence[int(row["canonical_message_sequence"])].append(row)
    for rows in delta_by_sequence.values():
        rows.sort(key=lambda item: int(item["level_index"]))
    for row in trades:
        sequence = int(row["canonical_message_sequence"])
        if sequence in trade_by_sequence:
            raise HistoricalReplayError("multiple trade rows share one canonical message sequence")
        trade_by_sequence[sequence] = row

    snapshot_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in snapshots:
        snapshot_groups[(str(row["symbol"]), str(row["connection_id"]))].append(row)

    event_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    integrity_rows: list[dict[str, Any]] = []
    global_event_index = 0
    global_observation_index = 0

    for symbol in config.symbols:
        symbol_sources = [row for row in source if str(row["symbol"]) == symbol]
        symbol_sources.sort(key=lambda item: int(item["canonical_message_sequence"]))
        by_connection: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in symbol_sources:
            by_connection[str(row["connection_id"])].append(row)
        staged_events: list[dict[str, Any]] = []
        connection_items = sorted(
            by_connection.items(),
            key=lambda item: min(
                int(row["connection_started_utc_ns"])
                for row in snapshot_groups.get((symbol, item[0]), [])
            ),
        )
        previous_connection_receive_end: int | None = None
        for connection_id, messages in connection_items:
            snapshot_rows = snapshot_groups.get((symbol, connection_id))
            if not snapshot_rows:
                raise HistoricalReplayError(f"missing snapshot for {symbol}/{connection_id}")
            snapshot_rows.sort(key=lambda item: (str(item["side"]), int(item["level_index"])))
            connection_start = int(snapshot_rows[0]["connection_started_utc_ns"])
            if (
                previous_connection_receive_end is not None
                and connection_start < previous_connection_receive_end
            ):
                raise HistoricalReplayError("canonical replay connections overlap in receive time")
            staged_events.append(
                {
                    "symbol": symbol,
                    "connection_id": connection_id,
                    "event_kind": "connection_reset",
                    "event_time_ns": connection_start,
                    "receive_time_ns": connection_start,
                    "available_time_ns": connection_start,
                    "canonical_message_sequence": int(messages[0]["canonical_message_sequence"]),
                    "source_sequence_start": 0,
                    "source_sequence_end": 0,
                    "row_count": 0,
                    "payload": {},
                    "snapshot_timestamp_semantics": "internal_reconnect_boundary",
                    "priority": -1,
                }
            )
            last_update_id = int(snapshot_rows[0]["last_update_id"])
            if any(int(row["last_update_id"]) != last_update_id for row in snapshot_rows):
                raise HistoricalReplayError("snapshot levels disagree on last_update_id")
            bridge_source: dict[str, Any] | None = None
            bridge_rows: list[dict[str, Any]] | None = None
            for message in messages:
                sequence = int(message["canonical_message_sequence"])
                candidate_rows = delta_by_sequence.get(sequence)
                if candidate_rows and int(
                    candidate_rows[0]["first_update_id"]
                ) <= last_update_id + 1 <= int(candidate_rows[0]["final_update_id"]):
                    bridge_source = message
                    bridge_rows = candidate_rows
                    break
            if bridge_source is None or bridge_rows is None:
                raise HistoricalReplayError("connection has no snapshot-bridging depth batch")
            synchronization_receive = int(bridge_source["received_utc_ns"])
            snapshot_payload = {
                "bids": [
                    [int(row["price_ticks"]), int(row["quantity_lots"])]
                    for row in snapshot_rows
                    if row["side"] == "bid"
                ],
                "asks": [
                    [int(row["price_ticks"]), int(row["quantity_lots"])]
                    for row in snapshot_rows
                    if row["side"] == "ask"
                ],
                "last_update_id": last_update_id,
            }
            staged_events.append(
                {
                    "symbol": symbol,
                    "connection_id": connection_id,
                    "event_kind": "snapshot",
                    "event_time_ns": int(snapshot_rows[0]["connection_started_utc_ns"]),
                    "receive_time_ns": synchronization_receive,
                    "available_time_ns": synchronization_receive
                    + config.observation_processing_delay_ns,
                    "canonical_message_sequence": int(bridge_source["canonical_message_sequence"]),
                    "source_sequence_start": last_update_id,
                    "source_sequence_end": last_update_id,
                    "row_count": len(snapshot_rows),
                    "payload": snapshot_payload,
                    "snapshot_timestamp_semantics": (
                        "connection_start_proxy_suppressed_until_sequence_bridge"
                    ),
                    "priority": 0,
                }
            )
            depth_count = 0
            trade_count = 0
            current_update_id = last_update_id
            bridge_first = int(bridge_rows[0]["first_update_id"])
            bridge_final = int(bridge_rows[0]["final_update_id"])
            for message in messages:
                sequence = int(message["canonical_message_sequence"])
                if sequence not in source_by_sequence:
                    raise HistoricalReplayError("source message sequence lookup failed")
                if sequence in delta_by_sequence:
                    rows = delta_by_sequence[sequence]
                    first = int(rows[0]["first_update_id"])
                    final = int(rows[0]["final_update_id"])
                    expected = current_update_id + 1
                    if final < expected or first > expected:
                        raise HistoricalReplayError("historical depth sequence is stale or gapped")
                    current_update_id = final
                    updates = [
                        {
                            "side": str(row["side"]),
                            "price_ticks": int(row["price_ticks"]),
                            "quantity_lots": int(row["quantity_lots"]),
                            "is_delete": bool(row["is_delete"]),
                        }
                        for row in rows
                    ]
                    staged_events.append(
                        {
                            "symbol": symbol,
                            "connection_id": connection_id,
                            "event_kind": "depth_batch",
                            "event_time_ns": int(rows[0]["event_time_ns"]),
                            "receive_time_ns": int(rows[0]["received_utc_ns"]),
                            "available_time_ns": int(rows[0]["received_utc_ns"])
                            + config.observation_processing_delay_ns,
                            "canonical_message_sequence": sequence,
                            "source_sequence_start": first,
                            "source_sequence_end": final,
                            "row_count": len(rows),
                            "payload": updates,
                            "snapshot_timestamp_semantics": "not_applicable",
                            "priority": 1,
                        }
                    )
                    depth_count += 1
                elif sequence in trade_by_sequence:
                    trade = trade_by_sequence[sequence]
                    staged_events.append(
                        {
                            "symbol": symbol,
                            "connection_id": connection_id,
                            "event_kind": "trade",
                            "event_time_ns": int(trade["event_time_ns"]),
                            "receive_time_ns": int(trade["received_utc_ns"]),
                            "available_time_ns": int(trade["received_utc_ns"])
                            + config.observation_processing_delay_ns,
                            "canonical_message_sequence": sequence,
                            "source_sequence_start": int(trade["trade_id"]),
                            "source_sequence_end": int(trade["trade_id"]),
                            "row_count": 1,
                            "payload": {
                                "trade_id": int(trade["trade_id"]),
                                "price_ticks": int(trade["price_ticks"]),
                                "quantity_lots": int(trade["quantity_lots"]),
                                "aggressor_side": (
                                    "sell" if bool(trade["buyer_is_maker"]) else "buy"
                                ),
                            },
                            "snapshot_timestamp_semantics": "not_applicable",
                            "priority": 2,
                        }
                    )
                    trade_count += 1
                else:
                    raise HistoricalReplayError("source message has no canonical event rows")
            previous_connection_receive_end = max(
                int(message["received_utc_ns"]) for message in messages
            )
            integrity_rows.append(
                {
                    "symbol": symbol,
                    "connection_id": connection_id,
                    "snapshot_last_update_id": last_update_id,
                    "bridging_first_update_id": bridge_first,
                    "bridging_final_update_id": bridge_final,
                    "depth_batch_count": depth_count,
                    "trade_count": trade_count,
                    "sequence_gap_count": 0,
                    "crossed_book_count": 0,
                    "synchronized": True,
                    "snapshot_timestamp_semantics": (
                        "connection_start_proxy_suppressed_until_sequence_bridge"
                    ),
                }
            )

        staged_events.sort(
            key=lambda item: (
                int(item["available_time_ns"]),
                int(item["priority"]),
                int(item["canonical_message_sequence"]),
            )
        )
        (
            materialized_events,
            materialized_observations,
            global_event_index,
            global_observation_index,
        ) = _materialize_symbol_events(
            staged_events, config, symbol, global_event_index, global_observation_index
        )
        event_rows.extend(materialized_events)
        observation_rows.extend(materialized_observations)

    target.mkdir(parents=True)
    schemas = _schemas()
    artifacts = []
    for name, rows in (
        ("replay_events", event_rows),
        ("replay_observations", observation_rows),
        ("connection_integrity", integrity_rows),
    ):
        order, schema = schemas[name]
        artifacts.append(write_columnar_table(target, name, rows, schema, order).to_dict())

    config_hash = _sha256_json(config.to_dict())
    research_admissible = bool(manifest.get("research_admissible")) and not sample
    output_manifest = {
        "schema_version": 1,
        "step": 15,
        "replay_id": identifier,
        "software_version": __version__,
        "venue_id": manifest.get("venue_id"),
        "symbols": list(config.symbols),
        "source_dataset_id": manifest.get("dataset_id"),
        "source_dataset_manifest_sha256": hashlib.sha256(
            canonical_manifest_path.read_bytes()
        ).hexdigest(),
        "source_dataset_classification": classification,
        "source_dataset_verification": verification,
        "replay_config_sha256": config_hash,
        "checkpoint_policy": config.checkpoint_policy,
        "observation_processing_delay_ns": config.observation_processing_delay_ns,
        "queue_position_semantics": config.queue_position_semantics,
        "exact_fifo_reconstructed": False,
        "market_impact_semantics": config.market_impact_semantics,
        "endogenous_impact_modelled": False,
        "ghost_small_agent_assumption": True,
        "snapshot_timestamp_semantics": ("connection_start_proxy_suppressed_until_sequence_bridge"),
        "research_admissible": research_admissible,
        "research_blockers": (
            ["synthetic_sample_input", "exact_snapshot_fetch_timestamp_unavailable"]
            if sample
            else ["exact_snapshot_fetch_timestamp_unavailable"]
        ),
        "research_specification_changed": False,
        "event_count": len(event_rows),
        "observation_count": len(observation_rows),
        "connection_count": len(integrity_rows),
        "tables": artifacts,
    }
    manifest_path = target / "replay-manifest.json"
    write_immutable_json(manifest_path, output_manifest)
    write_immutable_json(
        target / "replay-manifest.sha256.json",
        {"sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
    )
    return manifest_path
