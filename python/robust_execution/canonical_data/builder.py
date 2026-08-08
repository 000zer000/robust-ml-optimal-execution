"""Build immutable Step 14 canonical event tables from validated Step 12 data."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from robust_execution import __version__
from robust_execution.canonical_data.config import CanonicalDataConfig
from robust_execution.canonical_data.models import TableArtifact, write_columnar_table
from robust_execution.canonical_data.parquet import ParquetExportError, write_parquet_table
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.data_capture.verify import verify_capture_manifest
from robust_execution.data_validation.verify import verify_data_validation_report


class CanonicalDataError(RuntimeError):
    """Raised when validated input cannot be canonicalised without ambiguity."""


def decimal_to_units(value: object, increment: Decimal, field: str) -> int:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CanonicalDataError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise CanonicalDataError(f"{field} must be finite and non-negative")
    units = parsed / increment
    integral = units.to_integral_value()
    if units != integral:
        raise CanonicalDataError(
            f"{field}={parsed} is not an exact multiple of increment {increment}"
        )
    result = int(integral)
    if result < 0 or result > 9_223_372_036_854_775_807:
        raise CanonicalDataError(f"{field} fixed-point value is outside int64")
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalDataError(f"cannot read {path}: {exc}") from exc


def _read_gzip_json(path: Path) -> Any:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalDataError(f"cannot read {path}: {exc}") from exc


def _selected_days(report: dict[str, Any], config: CanonicalDataConfig) -> tuple[list[str], str]:
    days = report.get("days")
    if not isinstance(days, list):
        raise CanonicalDataError("validation report days are missing")
    selected: list[str] = []
    if config.output_tier == "processed":
        for item in days:
            if isinstance(item, dict) and item.get("admission_status") == "admitted":
                selected.append(str(item.get("day")))
        if not selected:
            raise CanonicalDataError("processed output requires at least one research-admitted day")
        return sorted(selected), "research_processed"
    for item in days:
        if not isinstance(item, dict):
            continue
        if (
            item.get("structural_status") == "valid"
            and item.get("admission_status") == "fixture_valid_not_admissible"
        ):
            selected.append(str(item.get("day")))
    if not selected or not config.input_policy.allow_structurally_valid_fixture_sample:
        raise CanonicalDataError("sample output requires a structurally valid fixture day")
    return sorted(selected), "sample_only_non_research"


def _raw_records(manifest_path: Path, selected_days: set[str]) -> list[dict[str, Any]]:
    manifest = _read_json(manifest_path)
    root = manifest_path.parent
    records: list[dict[str, Any]] = []
    source_index = 0
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise CanonicalDataError("capture manifest artifacts are missing")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        relative = artifact.get("relative_path")
        if not isinstance(relative, str) or "segment-" not in Path(relative).name:
            continue
        parts = Path(relative).parts
        if len(parts) < 3 or parts[-2] not in selected_days:
            continue
        try:
            with gzip.open(root / relative, "rt", encoding="utf-8", newline="") as handle:
                for line_number, line in enumerate(handle, 1):
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise CanonicalDataError(
                            f"record is not an object: {relative}:{line_number}"
                        )
                    value["_source_record_index"] = source_index
                    value["_source_relative_path"] = relative
                    value["_source_line_number"] = line_number
                    records.append(value)
                    source_index += 1
        except (OSError, json.JSONDecodeError) as exc:
            raise CanonicalDataError(f"cannot read raw segment {relative}: {exc}") from exc
    return records


def _deduplicate(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: dict[tuple[object, ...], str] = {}
    for record in records:
        try:
            wrapper = json.loads(str(record["raw_payload_utf8"]))
            payload = wrapper["data"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CanonicalDataError("validated raw record cannot be parsed") from exc
        event_type = payload.get("e")
        key: tuple[object, ...]
        if event_type == "trade":
            key = ("trade", payload.get("s"), payload.get("t"))
        elif event_type == "depthUpdate":
            key = ("depth", payload.get("s"), payload.get("U"), payload.get("u"))
        else:
            raise CanonicalDataError(f"unsupported validated event type: {event_type}")
        digest = str(record.get("raw_payload_sha256"))
        previous = seen.get(key)
        if previous is None:
            seen[key] = digest
            unique.append(record)
            continue
        if previous != digest:
            raise CanonicalDataError(f"conflicting duplicate natural key: {key}")
        duplicates.append(
            {
                "duplicate_sequence": len(duplicates),
                "event_kind": str(key[0]),
                "symbol": str(payload.get("s")),
                "natural_key": ":".join(str(part) for part in key[2:]),
                "raw_payload_sha256": digest,
                "source_record_index": int(record["_source_record_index"]),
                "disposition": "exact_duplicate_dropped",
            }
        )
    return unique, duplicates


def _schemas() -> dict[str, tuple[tuple[str, ...], dict[str, object]]]:
    definitions: dict[str, tuple[tuple[str, ...], dict[str, object]]] = {}

    def add(name: str, columns: tuple[tuple[str, str, bool], ...]) -> None:
        order = tuple(item[0] for item in columns)
        definitions[name] = (
            order,
            {
                "schema_version": 1,
                "table_name": name,
                "columns": [
                    {"name": column, "logical_type": logical, "nullable": nullable}
                    for column, logical, nullable in columns
                ],
            },
        )

    provenance = (
        ("dataset_id", "utf8", False),
        ("venue_id", "utf8", False),
        ("symbol", "utf8", False),
        ("source_run_id", "utf8", False),
        ("source_record_index", "int64", False),
        ("source_relative_path", "utf8", False),
        ("source_line_number", "int64", False),
        ("raw_payload_sha256", "sha256_hex", False),
    )
    add(
        "source_records",
        (
            *provenance,
            ("canonical_message_sequence", "int64", False),
            ("connection_id", "utf8", False),
            ("message_index", "int64", False),
            ("stream", "utf8", False),
            ("event_type", "utf8", False),
            ("event_time_ns", "timestamp_ns_utc", False),
            ("received_utc_ns", "timestamp_ns_utc", False),
            ("received_monotonic_ns", "duration_ns", False),
        ),
    )
    add(
        "book_deltas",
        (
            *provenance,
            ("canonical_message_sequence", "int64", False),
            ("canonical_row_sequence", "int64", False),
            ("level_index", "int64", False),
            ("event_time_ns", "timestamp_ns_utc", False),
            ("received_utc_ns", "timestamp_ns_utc", False),
            ("first_update_id", "int64", False),
            ("final_update_id", "int64", False),
            ("side", "enum:bid|ask", False),
            ("price_ticks", "int64", False),
            ("quantity_lots", "int64", False),
            ("is_delete", "bool", False),
        ),
    )
    add(
        "trades",
        (
            *provenance,
            ("canonical_message_sequence", "int64", False),
            ("canonical_row_sequence", "int64", False),
            ("event_time_ns", "timestamp_ns_utc", False),
            ("trade_time_ns", "timestamp_ns_utc", False),
            ("received_utc_ns", "timestamp_ns_utc", False),
            ("trade_id", "int64", False),
            ("price_ticks", "int64", False),
            ("quantity_lots", "int64", False),
            ("buyer_is_maker", "bool", False),
            ("best_price_match", "bool", False),
        ),
    )
    add(
        "book_snapshots",
        (
            ("dataset_id", "utf8", False),
            ("venue_id", "utf8", False),
            ("symbol", "utf8", False),
            ("source_run_id", "utf8", False),
            ("snapshot_relative_path", "utf8", False),
            ("connection_id", "utf8", False),
            ("connection_started_utc_ns", "timestamp_ns_utc", False),
            ("last_update_id", "int64", False),
            ("canonical_row_sequence", "int64", False),
            ("level_index", "int64", False),
            ("side", "enum:bid|ask", False),
            ("price_ticks", "int64", False),
            ("quantity_lots", "int64", False),
        ),
    )
    add(
        "duplicate_records",
        (
            ("duplicate_sequence", "int64", False),
            ("event_kind", "utf8", False),
            ("symbol", "utf8", False),
            ("natural_key", "utf8", False),
            ("raw_payload_sha256", "sha256_hex", False),
            ("source_record_index", "int64", False),
            ("disposition", "enum:exact_duplicate_dropped", False),
        ),
    )
    add(
        "instrument_definitions",
        (
            ("venue_id", "utf8", False),
            ("symbol", "utf8", False),
            ("price_increment_decimal", "decimal_string", False),
            ("quantity_increment_decimal", "decimal_string", False),
            ("price_unit_name", "utf8", False),
            ("quantity_unit_name", "utf8", False),
            ("definition_source", "utf8", False),
        ),
    )
    return definitions


def _provenance(record: dict[str, Any], dataset_id: str, venue_id: str) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "venue_id": venue_id,
        "symbol": str(record["symbol"]),
        "source_run_id": str(record["run_id"]),
        "source_record_index": int(record["_source_record_index"]),
        "source_relative_path": str(record["_source_relative_path"]),
        "source_line_number": int(record["_source_line_number"]),
        "raw_payload_sha256": str(record["raw_payload_sha256"]),
    }


def _build_rows(
    records: list[dict[str, Any]],
    config: CanonicalDataConfig,
    dataset_id: str,
) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_delta_row = 0
    global_trade_row = 0
    for message_sequence, record in enumerate(records):
        wrapper = json.loads(str(record["raw_payload_utf8"]))
        payload = wrapper["data"]
        symbol = str(payload["s"])
        instrument = config.instrument(symbol)
        event_time_ns = int(payload["E"]) * 1000
        provenance = _provenance(record, dataset_id, config.venue_id)
        tables["source_records"].append(
            provenance
            | {
                "canonical_message_sequence": message_sequence,
                "connection_id": str(record["connection_id"]),
                "message_index": int(record["message_index"]),
                "stream": str(record["stream"]),
                "event_type": str(payload["e"]),
                "event_time_ns": event_time_ns,
                "received_utc_ns": int(record["received_utc_ns"]),
                "received_monotonic_ns": int(record["received_monotonic_ns"]),
            }
        )
        if payload["e"] == "depthUpdate":
            level_index = 0
            for side, levels in (("bid", payload.get("b", [])), ("ask", payload.get("a", []))):
                if not isinstance(levels, list):
                    raise CanonicalDataError("depth levels must be arrays")
                for level in levels:
                    if not isinstance(level, list) or len(level) != 2:
                        raise CanonicalDataError("depth level must be [price, quantity]")
                    quantity = decimal_to_units(
                        level[1], instrument.quantity_decimal, "depth quantity"
                    )
                    tables["book_deltas"].append(
                        provenance
                        | {
                            "canonical_message_sequence": message_sequence,
                            "canonical_row_sequence": global_delta_row,
                            "level_index": level_index,
                            "event_time_ns": event_time_ns,
                            "received_utc_ns": int(record["received_utc_ns"]),
                            "first_update_id": int(payload["U"]),
                            "final_update_id": int(payload["u"]),
                            "side": side,
                            "price_ticks": decimal_to_units(
                                level[0], instrument.price_decimal, "depth price"
                            ),
                            "quantity_lots": quantity,
                            "is_delete": quantity == 0,
                        }
                    )
                    level_index += 1
                    global_delta_row += 1
        elif payload["e"] == "trade":
            tables["trades"].append(
                provenance
                | {
                    "canonical_message_sequence": message_sequence,
                    "canonical_row_sequence": global_trade_row,
                    "event_time_ns": event_time_ns,
                    "trade_time_ns": int(payload["T"]) * 1000,
                    "received_utc_ns": int(record["received_utc_ns"]),
                    "trade_id": int(payload["t"]),
                    "price_ticks": decimal_to_units(
                        payload["p"], instrument.price_decimal, "trade price"
                    ),
                    "quantity_lots": decimal_to_units(
                        payload["q"], instrument.quantity_decimal, "trade quantity"
                    ),
                    "buyer_is_maker": bool(payload["m"]),
                    "best_price_match": bool(payload["M"]),
                }
            )
            global_trade_row += 1
    return tables


def _snapshot_rows(
    manifest_path: Path, config: CanonicalDataConfig, dataset_id: str, selected_days: set[str]
) -> list[dict[str, Any]]:
    manifest = _read_json(manifest_path)
    root = manifest_path.parent
    connections = {
        str(item["connection_id"]): item
        for item in manifest.get("connections", [])
        if isinstance(item, dict)
    }
    starts = {name: int(item["started_utc_ns"]) for name, item in connections.items()}
    rows: list[dict[str, Any]] = []
    artifacts = manifest.get("artifacts", [])
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        relative = artifact.get("relative_path")
        if not isinstance(relative, str) or not relative.startswith("snapshots/"):
            continue
        parts = Path(relative).parts
        symbol = parts[1]
        stem = Path(parts[-1]).name.removesuffix(".json.gz")
        if "-" not in stem:
            raise CanonicalDataError(f"cannot parse snapshot connection: {relative}")
        connection_id = stem.rsplit("-", 1)[0]
        if connection_id not in starts:
            raise CanonicalDataError(f"snapshot connection not in manifest: {connection_id}")
        connection_day = (
            datetime.fromtimestamp(starts[connection_id] / 1_000_000_000, tz=UTC).date().isoformat()
        )
        if connection_day not in selected_days:
            continue
        snapshot = _read_gzip_json(root / relative)
        instrument = config.instrument(symbol)
        row_index = 0
        for side, levels in (("bid", snapshot.get("bids", [])), ("ask", snapshot.get("asks", []))):
            for level_index, level in enumerate(levels):
                rows.append(
                    {
                        "dataset_id": dataset_id,
                        "venue_id": config.venue_id,
                        "symbol": symbol,
                        "source_run_id": str(manifest["run_id"]),
                        "snapshot_relative_path": relative,
                        "connection_id": connection_id,
                        "connection_started_utc_ns": starts[connection_id],
                        "last_update_id": int(snapshot["lastUpdateId"]),
                        "canonical_row_sequence": len(rows),
                        "level_index": level_index,
                        "side": side,
                        "price_ticks": decimal_to_units(
                            level[0], instrument.price_decimal, "snapshot price"
                        ),
                        "quantity_lots": decimal_to_units(
                            level[1], instrument.quantity_decimal, "snapshot quantity"
                        ),
                    }
                )
                row_index += 1
    return rows


def _parquet_status(config: CanonicalDataConfig) -> dict[str, object]:
    available = importlib.util.find_spec("pyarrow") is not None
    if config.output_tier == "processed" and config.format_policy.parquet_required_for_processed:
        if not available:
            raise CanonicalDataError(
                "processed research output requires pyarrow==25.0.0/Parquet; engine is unavailable"
            )
        return {
            "required": True,
            "engine": "pyarrow",
            "available": True,
            "written": False,
            "artifacts": [],
        }
    return {
        "required": False,
        # Optional host packages must not change the deterministic sample manifest. PyArrow
        # availability is evaluated only for the processed research tier above.
        "engine": None,
        "available": False,
        "written": False,
        "reason": "sample fixture uses deterministic base layer; not a research dataset",
    }


def build_canonical_dataset(
    capture_manifest_path: Path,
    validation_report_path: Path,
    config: CanonicalDataConfig,
    output_root: Path,
    *,
    dataset_id: str | None = None,
) -> Path:
    """Construct an immutable canonical dataset from independently validated input."""
    capture_verification = verify_capture_manifest(capture_manifest_path)
    validation_verification = verify_data_validation_report(validation_report_path)
    capture_manifest = _read_json(capture_manifest_path)
    report = _read_json(validation_report_path)
    if report.get("source_run_id") != capture_manifest.get("run_id"):
        raise CanonicalDataError("validation report and capture manifest refer to different runs")
    if report.get("source_manifest_sha256") != capture_verification.get("manifest_sha256"):
        raise CanonicalDataError("validation report source-manifest hash does not match")
    if config.input_policy.require_verified_capture and not validation_verification:
        raise CanonicalDataError("source validation could not be verified")
    selected_days, classification = _selected_days(report, config)
    if (
        config.output_tier == "sample"
        and capture_manifest.get("data_origin") != "synthetic_transport_fixture"
    ):
        raise CanonicalDataError("sample tier is reserved for the deterministic fixture")
    identifier = dataset_id or f"{capture_manifest['run_id']}-canonical-v1"
    target = output_root / identifier
    if target.exists():
        raise FileExistsError(f"canonical dataset already exists: {target}")
    target.mkdir(parents=True)
    try:
        records = _raw_records(capture_manifest_path, set(selected_days))
        unique, duplicates = _deduplicate(records)
        rows = _build_rows(unique, config, identifier)
        rows["book_snapshots"] = _snapshot_rows(
            capture_manifest_path, config, identifier, set(selected_days)
        )
        rows["duplicate_records"] = duplicates
        rows["instrument_definitions"] = [
            {
                "venue_id": config.venue_id,
                "symbol": item.symbol,
                "price_increment_decimal": item.price_increment,
                "quantity_increment_decimal": item.quantity_increment,
                "price_unit_name": "price_tick",
                "quantity_unit_name": "quantity_lot",
                "definition_source": item.source,
            }
            for item in config.instruments
        ]
        schemas = _schemas()
        table_artifacts: list[TableArtifact] = []
        for table_name in (
            "instrument_definitions",
            "source_records",
            "book_snapshots",
            "book_deltas",
            "trades",
            "duplicate_records",
        ):
            order, schema = schemas[table_name]
            table_artifacts.append(
                write_columnar_table(target, table_name, rows.get(table_name, []), schema, order)
            )
        config_path = target / "canonical-config.json"
        write_immutable_json(config_path, config.to_dict())
        parquet = _parquet_status(config)
        if parquet["required"]:
            parquet_artifacts: list[dict[str, object]] = []
            try:
                for table_name in (
                    "instrument_definitions",
                    "source_records",
                    "book_snapshots",
                    "book_deltas",
                    "trades",
                    "duplicate_records",
                ):
                    order, schema = schemas[table_name]
                    parquet_path = target / "tables" / table_name / "table.parquet"
                    artifact = write_parquet_table(
                        parquet_path, rows.get(table_name, []), schema, order
                    )
                    artifact["relative_path"] = str(parquet_path.relative_to(target))
                    artifact["table_name"] = table_name
                    parquet_artifacts.append(artifact)
            except ParquetExportError as exc:
                raise CanonicalDataError(str(exc)) from exc
            parquet["written"] = True
            parquet["artifacts"] = parquet_artifacts
        manifest = {
            "schema_version": 1,
            "step": 14,
            "dataset_id": identifier,
            "dataset_classification": classification,
            "research_admissible": classification == "research_processed",
            "venue_id": config.venue_id,
            "symbols": list(config.symbols),
            "selected_days": selected_days,
            "source_run_id": capture_manifest["run_id"],
            "source_manifest_sha256": capture_verification["manifest_sha256"],
            "validation_id": report["validation_id"],
            "validation_report_sha256": validation_verification["report_sha256"],
            "data_origin": capture_manifest["data_origin"],
            "software_version": __version__,
            "physical_format": "re_columnar_v1",
            "compression": "gzip",
            "canonical_order": "capture_artifact_order_then_record_order_then_payload_level_order",
            "fixed_point_conversion": "exact_increment_multiple_only",
            "missing_events_repaired": False,
            "research_specification_changed": False,
            "duplicate_policy": "drop_exact_natural_key_duplicates_reject_conflicts",
            "input_records": len(records),
            "unique_messages": len(unique),
            "exact_duplicates_dropped": len(duplicates),
            "tables": [item.to_dict() for item in table_artifacts],
            "canonical_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "parquet": parquet,
            "publication": {
                "contains_raw_payloads": False,
                "contains_reconstructive_market_data": True,
                "public_redistribution_cleared": False,
            },
        }
        write_immutable_json(target / "dataset-manifest.json", manifest)
        write_immutable_json(
            target / "dataset-manifest.sha256.json",
            {"sha256": hashlib.sha256((target / "dataset-manifest.json").read_bytes()).hexdigest()},
        )
        return target / "dataset-manifest.json"
    except Exception:
        if target.exists() and not any(target.iterdir()):
            target.rmdir()
        raise
