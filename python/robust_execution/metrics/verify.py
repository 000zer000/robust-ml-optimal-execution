"""Independent verification of Step 17 execution metrics.

The verifier intentionally reconstructs the detailed ledger and aggregate tail
statistics in Python rather than trusting the C++ output fields.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median, variance
from typing import Any


class MetricsVerificationError(ValueError):
    """Raised when metric evidence is malformed, inconsistent, or tampered."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MetricsVerificationError(f"JSON object required: {path}")
    return value


def _require_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MetricsVerificationError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise MetricsVerificationError(f"{name} is below its minimum")
    return value


def _require_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise MetricsVerificationError(f"{name} must be a finite number")
    return float(value)


def _close(lhs: float, rhs: float) -> bool:
    return math.isclose(lhs, rhs, rel_tol=1e-12, abs_tol=1e-12)


def _exact_notional(instrument: dict[str, Any], price: int, quantity: int) -> int:
    if price < 0 or quantity < 0:
        raise MetricsVerificationError("price and quantity must be non-negative")
    numerator = (
        price
        * quantity
        * _require_int(instrument.get("tick_numerator"), "tick_numerator", minimum=1)
        * _require_int(instrument.get("lot_numerator"), "lot_numerator", minimum=1)
        * _require_int(
            instrument.get("quote_atom_denominator"),
            "quote_atom_denominator",
            minimum=1,
        )
    )
    denominator = (
        _require_int(instrument.get("tick_denominator"), "tick_denominator", minimum=1)
        * _require_int(instrument.get("lot_denominator"), "lot_denominator", minimum=1)
        * _require_int(
            instrument.get("quote_atom_numerator"),
            "quote_atom_numerator",
            minimum=1,
        )
    )
    quotient, remainder = divmod(numerator, denominator)
    if remainder:
        raise MetricsVerificationError("ledger notional is not exactly representable")
    if quotient > 2**63 - 1:
        raise MetricsVerificationError("ledger notional exceeds signed quote-atom range")
    return quotient


def _directional_cost(side: str, execution: int, benchmark: int, fees: int) -> int:
    if side == "buy":
        return execution - benchmark + fees
    if side == "sell":
        return benchmark - execution + fees
    raise MetricsVerificationError("side must be buy or sell")


def _nearest_rank(values: list[float], probability: float) -> float:
    rank = max(1, math.ceil(probability * len(values)))
    return values[rank - 1]


def _fractional_tail_mean(values: list[float], probability: float) -> float:
    target = (1.0 - probability) * len(values)
    if target <= 0.0:
        return values[-1]
    remaining = target
    total = 0.0
    for value in reversed(values):
        if remaining <= 0.0:
            break
        weight = min(1.0, remaining)
        total += weight * value
        remaining -= weight
    return total / target


def _verify_detailed_ledger(report: dict[str, Any]) -> dict[str, Any]:
    ledger = report.get("detailed_ledger")
    metrics = report.get("detailed_episode")
    if not isinstance(ledger, dict) or not isinstance(metrics, dict):
        raise MetricsVerificationError("detailed ledger and metrics objects are required")
    side = ledger.get("side")
    parent_quantity = _require_int(ledger.get("parent_quantity_lots"), "parent_quantity", minimum=1)
    arrival_price = _require_int(ledger.get("arrival_price_ticks"), "arrival_price", minimum=1)
    instrument = ledger.get("instrument")
    fills = ledger.get("fills")
    if not isinstance(instrument, dict) or not isinstance(fills, list) or not fills:
        raise MetricsVerificationError("detailed instrument and fills are required")

    execution_ids: set[int] = set()
    filled = 0
    notional = 0
    fees = 0
    passive = 0
    aggressive = 0
    unknown = 0
    terminal_quantity = 0
    terminal_notional = 0
    terminal_fees = 0
    previous_time = _require_int(ledger.get("start_time_ns"), "start_time_ns")
    end_time = _require_int(ledger.get("end_time_ns"), "end_time_ns")
    expected_inventory: list[tuple[int, int]] = [(previous_time, parent_quantity)]
    end_inserted = False
    fill_map: dict[int, dict[str, Any]] = {}
    for row in fills:
        if not isinstance(row, dict):
            raise MetricsVerificationError("fill rows must be objects")
        execution_id = _require_int(row.get("execution_id"), "execution_id", minimum=1)
        if execution_id in execution_ids:
            raise MetricsVerificationError("duplicate execution ID")
        execution_ids.add(execution_id)
        price = _require_int(row.get("price_ticks"), "fill price", minimum=1)
        quantity = _require_int(row.get("quantity_lots"), "fill quantity", minimum=1)
        fill_time = _require_int(row.get("fill_time_ns"), "fill_time_ns")
        if fill_time < previous_time:
            raise MetricsVerificationError("fill times are not ordered")
        previous_time = fill_time
        if quantity > parent_quantity - filled:
            raise MetricsVerificationError("parent overfill")
        if not end_inserted and fill_time > end_time:
            expected_inventory.append((end_time, parent_quantity - filled))
            end_inserted = True
        value = _exact_notional(instrument, price, quantity)
        notional += value
        fees += _require_int(row.get("explicit_fee_quote_atoms"), "explicit fee")
        filled += quantity
        expected_inventory.append((fill_time, parent_quantity - filled))
        role = row.get("liquidity_role")
        if role == "maker":
            passive += quantity
        elif role == "taker":
            aggressive += quantity
        elif role == "unknown":
            unknown += quantity
        else:
            raise MetricsVerificationError("unknown liquidity role")
        if row.get("source") == "terminal_completion":
            terminal_quantity += quantity
            terminal_notional += value
            terminal_fees += _require_int(row.get("explicit_fee_quote_atoms"), "terminal fee")
        elif row.get("source") != "continuous":
            raise MetricsVerificationError("unknown fill source")
        fill_map[execution_id] = row
    if not end_inserted and expected_inventory[-1][0] < end_time:
        expected_inventory.append((end_time, parent_quantity - filled))

    if filled != parent_quantity:
        raise MetricsVerificationError("validation detailed episode must be complete")
    benchmark = _exact_notional(instrument, arrival_price, parent_quantity)
    shortfall = _directional_cost(str(side), notional, benchmark, fees)
    gross_cash = -notional if side == "buy" else notional
    net_cash = gross_cash - fees
    terminal_benchmark = _exact_notional(instrument, arrival_price, terminal_quantity)
    terminal_cost = (
        _directional_cost(str(side), terminal_notional, terminal_benchmark, terminal_fees)
        if terminal_quantity
        else 0
    )

    exact_fields = {
        "filled_quantity_lots": filled,
        "remaining_quantity_lots": 0,
        "gross_execution_notional_quote_atoms": notional,
        "gross_cash_flow_quote_atoms": gross_cash,
        "explicit_fees_quote_atoms": fees,
        "net_cash_flow_quote_atoms": net_cash,
        "implementation_shortfall_quote_atoms": shortfall,
        "terminal_quantity_lots": terminal_quantity,
        "terminal_completion_cost_quote_atoms": terminal_cost,
        "passive_quantity_lots": passive,
        "aggressive_quantity_lots": aggressive,
        "unknown_liquidity_quantity_lots": unknown,
    }
    for key, expected in exact_fields.items():
        if metrics.get(key) != expected:
            raise MetricsVerificationError(f"detailed metric mismatch: {key}")
    if metrics.get("complete") is not True or not _close(
        _require_number(metrics.get("completion_rate"), "completion_rate"), 1.0
    ):
        raise MetricsVerificationError("completion metrics differ")
    if not _close(
        _require_number(metrics.get("implementation_shortfall_bps"), "shortfall bps"),
        shortfall * 10_000.0 / benchmark,
    ):
        raise MetricsVerificationError("implementation shortfall bps differ")
    if not _close(
        _require_number(metrics.get("passive_fraction"), "passive_fraction"), passive / filled
    ) or not _close(
        _require_number(metrics.get("aggressive_fraction"), "aggressive_fraction"),
        aggressive / filled,
    ):
        raise MetricsVerificationError("liquidity fractions differ")

    inventory = metrics.get("inventory_trajectory")
    if not isinstance(inventory, list):
        raise MetricsVerificationError("inventory trajectory is required")
    actual_inventory = [
        (
            _require_int(row.get("timestamp_ns"), "inventory timestamp"),
            _require_int(row.get("remaining_lots"), "inventory remaining", minimum=0),
        )
        for row in inventory
        if isinstance(row, dict)
    ]
    if actual_inventory != expected_inventory:
        raise MetricsVerificationError("inventory trajectory differs from ledger reconstruction")

    markouts = ledger.get("markouts")
    adverse = metrics.get("adverse_selection")
    if not isinstance(markouts, list) or not isinstance(adverse, list):
        raise MetricsVerificationError("markout inputs and outputs are required")
    by_horizon: dict[int, tuple[int, int]] = {}
    seen_markouts: set[tuple[int, int]] = set()
    for row in markouts:
        if not isinstance(row, dict):
            raise MetricsVerificationError("markout rows must be objects")
        execution_id = _require_int(row.get("execution_id"), "markout execution", minimum=1)
        horizon = _require_int(row.get("horizon_ns"), "markout horizon", minimum=1)
        if (execution_id, horizon) in seen_markouts:
            raise MetricsVerificationError("duplicate markout")
        seen_markouts.add((execution_id, horizon))
        fill = fill_map.get(execution_id)
        if fill is None:
            raise MetricsVerificationError("markout references unknown execution")
        if _require_int(row.get("markout_time_ns"), "markout time") != (
            _require_int(fill.get("fill_time_ns"), "fill time") + horizon
        ):
            raise MetricsVerificationError("markout timestamp differs from horizon")
        quantity = _require_int(fill.get("quantity_lots"), "fill quantity", minimum=1)
        fill_notional = _exact_notional(
            instrument, _require_int(fill.get("price_ticks"), "fill price", minimum=1), quantity
        )
        mark_notional = _exact_notional(
            instrument,
            _require_int(row.get("markout_mid_price_ticks"), "markout price", minimum=1),
            quantity,
        )
        cost = fill_notional - mark_notional if side == "buy" else mark_notional - fill_notional
        prior_quantity, prior_cost = by_horizon.get(horizon, (0, 0))
        by_horizon[horizon] = (prior_quantity + quantity, prior_cost + cost)
    if len(adverse) != len(by_horizon):
        raise MetricsVerificationError("adverse-selection horizon count differs")
    for row in adverse:
        if not isinstance(row, dict):
            raise MetricsVerificationError("adverse-selection rows must be objects")
        horizon = _require_int(row.get("horizon_ns"), "adverse horizon", minimum=1)
        if horizon not in by_horizon:
            raise MetricsVerificationError("unexpected adverse-selection horizon")
        quantity, cost = by_horizon[horizon]
        denominator = _exact_notional(instrument, arrival_price, quantity)
        if row.get("observed_quantity_lots") != quantity or row.get(
            "directional_cost_quote_atoms"
        ) != cost:
            raise MetricsVerificationError("adverse-selection exact totals differ")
        if not _close(
            _require_number(row.get("coverage_fraction"), "markout coverage"), quantity / filled
        ) or not _close(
            _require_number(row.get("directional_cost_bps"), "adverse cost bps"),
            cost * 10_000.0 / denominator,
        ):
            raise MetricsVerificationError("adverse-selection rates differ")

    actions = ledger.get("actions")
    performance = ledger.get("performance")
    timings = ledger.get("decision_timings")
    if not isinstance(actions, dict) or not isinstance(performance, dict) or not isinstance(timings, list):
        raise MetricsVerificationError("activity, performance and timing ledgers are required")
    if metrics.get("actions") != actions:
        raise MetricsVerificationError("action counters differ")
    submits = _require_int(actions.get("submits"), "submits", minimum=0)
    cancels = _require_int(actions.get("cancels"), "cancels", minimum=0)
    expected_cancel_ratio = cancels / submits if submits else None
    actual_cancel_ratio = metrics.get("cancel_to_submit_ratio")
    if expected_cancel_ratio is None:
        if actual_cancel_ratio is not None:
            raise MetricsVerificationError("cancel ratio should be null")
    elif not _close(_require_number(actual_cancel_ratio, "cancel ratio"), expected_cancel_ratio):
        raise MetricsVerificationError("cancel ratio differs")
    events = _require_int(performance.get("events_processed"), "events_processed", minimum=0)
    wall = _require_int(performance.get("wall_time_ns"), "wall_time_ns", minimum=0)
    if events and not _close(
        _require_number(metrics.get("events_per_second"), "events_per_second"),
        events * 1_000_000_000.0 / wall,
    ):
        raise MetricsVerificationError("throughput differs")

    def verify_latency_summary(name: str, values: list[int]) -> None:
        summary = metrics.get(name)
        if not isinstance(summary, dict):
            raise MetricsVerificationError(f"{name} summary is required")
        ordered = sorted(values)
        if summary.get("count") != len(ordered):
            raise MetricsVerificationError(f"{name} count differs")
        if not ordered:
            expected = {
                "minimum_ns": 0,
                "maximum_ns": 0,
                "mean_ns": 0.0,
                "p50_ns": 0.0,
                "p95_ns": 0.0,
                "p99_ns": 0.0,
            }
        else:
            def nearest_rank(probability: float) -> float:
                rank = max(1, math.ceil(probability * len(ordered)))
                return float(ordered[rank - 1])

            expected = {
                "minimum_ns": ordered[0],
                "maximum_ns": ordered[-1],
                "mean_ns": mean(ordered),
                "p50_ns": nearest_rank(0.50),
                "p95_ns": nearest_rank(0.95),
                "p99_ns": nearest_rank(0.99),
            }
        for key, expected_value in expected.items():
            actual = summary.get(key)
            if isinstance(expected_value, int):
                if actual != expected_value:
                    raise MetricsVerificationError(f"{name} {key} differs")
            elif not _close(_require_number(actual, f"{name} {key}"), expected_value):
                raise MetricsVerificationError(f"{name} {key} differs")

    valid_timings = [row for row in timings if isinstance(row, dict)]
    if len(valid_timings) != len(timings):
        raise MetricsVerificationError("decision timings must be objects")
    controller = [
        _require_int(row.get("decision_end_ns"), "decision end")
        - _require_int(row.get("decision_start_ns"), "decision start")
        for row in valid_timings
    ]
    staleness = [
        _require_int(row.get("decision_start_ns"), "decision start")
        - _require_int(row.get("observation_cutoff_ns"), "observation cutoff")
        for row in valid_timings
    ]
    inference = [
        _require_int(row.get("inference_latency_ns"), "inference latency", minimum=0)
        for row in valid_timings
        if row.get("inference_latency_ns") is not None
    ]
    dispatch = [
        _require_int(row.get("action_dispatch_time_ns"), "action dispatch")
        - _require_int(row.get("decision_end_ns"), "decision end")
        for row in valid_timings
        if row.get("action_dispatch_time_ns") is not None
    ]
    if any(value < 0 for value in controller + staleness + dispatch):
        raise MetricsVerificationError("latency values must be non-negative")
    verify_latency_summary("controller_latency", controller)
    verify_latency_summary("observation_staleness", staleness)
    verify_latency_summary("inference_latency", inference)
    verify_latency_summary("action_dispatch_latency", dispatch)

    return {
        "episode_id": ledger.get("episode_id"),
        "shortfall_quote_atoms": shortfall,
        "shortfall_bps": shortfall * 10_000.0 / benchmark,
        "terminal_cost_quote_atoms": terminal_cost,
        "fill_count": len(fills),
        "markout_count": len(markouts),
    }


def _verify_aggregate(report: dict[str, Any]) -> dict[str, float | int]:
    rows = report.get("tail_episodes")
    aggregate = report.get("aggregate")
    if not isinstance(rows, list) or not isinstance(aggregate, dict) or len(rows) < 40:
        raise MetricsVerificationError("tail episode matrix is incomplete")
    identifiers: set[str] = set()
    losses: list[float] = []
    terminal_fractions: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            raise MetricsVerificationError("tail rows must be objects")
        episode_id = row.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id or episode_id in identifiers:
            raise MetricsVerificationError("tail episode IDs must be unique")
        identifiers.add(episode_id)
        losses.append(
            _require_number(row.get("implementation_shortfall_bps"), "tail loss")
        )
        terminal_fraction = _require_number(row.get("terminal_fraction"), "terminal fraction")
        if not 0.0 <= terminal_fraction <= 1.0:
            raise MetricsVerificationError("terminal fraction is outside [0, 1]")
        terminal_fractions.append(terminal_fraction)
    losses.sort()
    expected = {
        "episode_count": len(losses),
        "mean_bps": mean(losses),
        "sample_variance_bps2": variance(losses),
        "sample_stddev_bps": math.sqrt(variance(losses)),
        "minimum_bps": losses[0],
        "maximum_bps": losses[-1],
        "median_bps": median(losses),
        "var95_bps": _nearest_rank(losses, 0.95),
        "cvar95_bps": _fractional_tail_mean(losses, 0.95),
        "var99_bps": _nearest_rank(losses, 0.99),
        "cvar99_bps": _fractional_tail_mean(losses, 0.99),
        "mean_completion_rate": 1.0,
        "minimum_completion_rate": 1.0,
        "mean_terminal_fraction": mean(terminal_fractions),
    }
    for key, value in expected.items():
        actual = aggregate.get(key)
        if isinstance(value, int):
            if actual != value:
                raise MetricsVerificationError(f"aggregate mismatch: {key}")
        elif not _close(_require_number(actual, key), value):
            raise MetricsVerificationError(f"aggregate mismatch: {key}")
    if aggregate.get("quantile_method") != "empirical_nearest_rank" or aggregate.get(
        "cvar_method"
    ) != "fractional_worst_tail_mean":
        raise MetricsVerificationError("tail conventions differ")
    return {"episode_count": len(losses), "var95_bps": expected["var95_bps"], "cvar95_bps": expected["cvar95_bps"]}


def _verify_csvs(root: Path, report: dict[str, Any]) -> None:
    with (root / "episode-metrics.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1 or rows[0]["episode_id"] != report["detailed_episode"]["episode_id"]:
        raise MetricsVerificationError("episode metrics CSV differs")
    if int(rows[0]["implementation_shortfall_quote_atoms"]) != report["detailed_episode"][
        "implementation_shortfall_quote_atoms"
    ]:
        raise MetricsVerificationError("episode metrics CSV shortfall differs")

    with (root / "inventory-trajectory.csv").open(newline="", encoding="utf-8") as handle:
        inventory = list(csv.DictReader(handle))
    expected_inventory = report["detailed_episode"]["inventory_trajectory"]
    if len(inventory) != len(expected_inventory):
        raise MetricsVerificationError("inventory CSV row count differs")
    for csv_row, json_row in zip(inventory, expected_inventory, strict=True):
        if int(csv_row["timestamp_ns"]) != json_row["timestamp_ns"] or int(
            csv_row["remaining_lots"]
        ) != json_row["remaining_lots"]:
            raise MetricsVerificationError("inventory CSV differs")

    with (root / "tail-risk.csv").open(newline="", encoding="utf-8") as handle:
        tail = list(csv.DictReader(handle))
    if len(tail) != len(report["tail_episodes"]):
        raise MetricsVerificationError("tail CSV row count differs")
    for csv_row, json_row in zip(tail, report["tail_episodes"], strict=True):
        if csv_row["episode_id"] != json_row["episode_id"] or not _close(
            float(csv_row["implementation_shortfall_bps"]),
            float(json_row["implementation_shortfall_bps"]),
        ):
            raise MetricsVerificationError("tail CSV differs")


def verify_metrics_evidence(manifest_path: Path) -> dict[str, Any]:
    """Verify the immutable Step 17 evidence and independently reconstruct metrics."""

    manifest = _load_object(manifest_path)
    expected_keys = {
        "schema_version",
        "step",
        "report_id",
        "software_version",
        "research_status",
        "report_sha256",
        "artifacts",
    }
    if set(manifest) != expected_keys:
        raise MetricsVerificationError("metrics manifest keys differ")
    if manifest["schema_version"] != "metrics-evidence-manifest-v1" or manifest["step"] != 17:
        raise MetricsVerificationError("metrics manifest identity is invalid")
    if manifest["software_version"] != "0.14.0":
        raise MetricsVerificationError("metrics software version differs")
    if manifest["research_status"] != "synthetic_validation_only_non_research":
        raise MetricsVerificationError("metrics evidence cannot claim research status")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 4:
        raise MetricsVerificationError("metrics manifest must contain four artifacts")
    root = manifest_path.parent
    expected_paths = {
        "report.json",
        "episode-metrics.csv",
        "inventory-trajectory.csv",
        "tail-risk.csv",
    }
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            raise MetricsVerificationError("metrics artifact entry is invalid")
        relative = item["path"]
        if (
            not isinstance(relative, str)
            or relative in seen
            or relative.startswith("/")
            or ".." in Path(relative).parts
        ):
            raise MetricsVerificationError("metrics artifact path is invalid")
        seen.add(relative)
        path = root / relative
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256(path) != item["sha256"]
        ):
            raise MetricsVerificationError(f"metrics artifact verification failed: {relative}")
    if seen != expected_paths:
        raise MetricsVerificationError("metrics artifact set differs")

    report_path = root / "report.json"
    if _sha256(report_path) != manifest["report_sha256"]:
        raise MetricsVerificationError("metrics report hash differs")
    report = _load_object(report_path)
    if report.get("schema_version") != "metrics-validation-v1" or report.get("step") != 17:
        raise MetricsVerificationError("metrics report identity is invalid")
    if report.get("research_status") != "synthetic_validation_only_non_research" or report.get(
        "historical_results_claimed"
    ) is not False:
        raise MetricsVerificationError("metrics report overstates research evidence")
    for key in (
        "buy_sell_symmetry_passed",
        "incomplete_episode_rejected_from_aggregate",
        "independent_audit_passed",
        "exact_accounting_passed",
        "state_bounds_passed",
        "deterministic",
    ):
        if report.get(key) is not True:
            raise MetricsVerificationError(f"metrics validation gate failed: {key}")
    audit = report.get("detailed_audit")
    if not isinstance(audit, dict) or audit.get("passed") is not True or audit.get("issue_count") != 0:
        raise MetricsVerificationError("C++ independent audit did not pass")

    detailed = _verify_detailed_ledger(report)
    aggregate = _verify_aggregate(report)
    _verify_csvs(root, report)
    return {
        "report_id": manifest["report_id"],
        "detailed_episode_id": detailed["episode_id"],
        "implementation_shortfall_quote_atoms": detailed["shortfall_quote_atoms"],
        "terminal_cost_quote_atoms": detailed["terminal_cost_quote_atoms"],
        "aggregate_episode_count": aggregate["episode_count"],
        "var95_bps": aggregate["var95_bps"],
        "cvar95_bps": aggregate["cvar95_bps"],
        "independent_python_audit_passed": True,
        "historical_results_claimed": False,
    }
