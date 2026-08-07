from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Callable

import pytest

from robust_execution.metrics import MetricsVerificationError, verify_metrics_evidence

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/sample/metrics/step17-metrics-validation"


def copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "fixture"
    shutil.copytree(SOURCE, target)
    return target / "manifest.json"


def rewrite_json(path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def rehash_report(manifest_path: Path) -> None:
    report_path = manifest_path.parent / "report.json"
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    metadata["report_sha256"] = digest
    for item in metadata["artifacts"]:
        if item["path"] == "report.json":
            item["sha256"] = digest
            item["bytes"] = report_path.stat().st_size
    manifest_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def rehash_artifact(manifest_path: Path, relative: str) -> None:
    path = manifest_path.parent / relative
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for item in metadata["artifacts"]:
        if item["path"] == relative:
            item["sha256"] = digest
            item["bytes"] = path.stat().st_size
    manifest_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_verify_metrics_evidence() -> None:
    result = verify_metrics_evidence(SOURCE / "manifest.json")
    assert result["implementation_shortfall_quote_atoms"] == 83
    assert result["terminal_cost_quote_atoms"] == 52
    assert result["aggregate_episode_count"] == 40
    assert result["var95_bps"] == 165.0
    assert result["cvar95_bps"] == 172.5
    assert result["independent_python_audit_passed"]
    assert not result["historical_results_claimed"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(step=16),
        lambda value: value.update(software_version="0.13.0"),
        lambda value: value.update(research_status="research"),
        lambda value: value.update(report_sha256="0" * 64),
        lambda value: value.update(extra=True),
        lambda value: value.update(artifacts=[]),
        lambda value: value["artifacts"][0].update(path="../report.json"),
        lambda value: value["artifacts"][0].update(bytes=0),
        lambda value: value["artifacts"].append(value["artifacts"][0].copy()),
    ],
)
def test_manifest_tampering_is_rejected(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    manifest = copy_fixture(tmp_path)
    rewrite_json(manifest, mutation)
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(step=16),
        lambda value: value.update(research_status="research"),
        lambda value: value.update(historical_results_claimed=True),
        lambda value: value.update(buy_sell_symmetry_passed=False),
        lambda value: value.update(incomplete_episode_rejected_from_aggregate=False),
        lambda value: value.update(independent_audit_passed=False),
        lambda value: value.update(exact_accounting_passed=False),
        lambda value: value.update(state_bounds_passed=False),
        lambda value: value.update(deterministic=False),
        lambda value: value["detailed_audit"].update(passed=False),
        lambda value: value["detailed_audit"].update(issue_count=1),
        lambda value: value.update(tail_episodes=[]),
    ],
)
def test_report_gate_tampering_is_rejected(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    manifest = copy_fixture(tmp_path)
    report = manifest.parent / "report.json"
    rewrite_json(report, mutation)
    rehash_report(manifest)
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["detailed_ledger"]["fills"][1].update(execution_id=1),
        lambda value: value["detailed_ledger"]["fills"][0].update(quantity_lots=0),
        lambda value: value["detailed_ledger"]["fills"][0].update(price_ticks=0),
        lambda value: value["detailed_ledger"]["fills"][0].update(fill_time_ns=-1),
        lambda value: value["detailed_ledger"]["fills"][0].update(liquidity_role="bad"),
        lambda value: value["detailed_ledger"]["fills"][0].update(source="bad"),
        lambda value: value["detailed_ledger"]["instrument"].update(tick_denominator=3),
        lambda value: value["detailed_episode"].update(net_cash_flow_quote_atoms=0),
        lambda value: value["detailed_episode"].update(implementation_shortfall_bps=0),
        lambda value: value["detailed_episode"].update(passive_fraction=0),
        lambda value: value["detailed_episode"].update(inventory_trajectory=[]),
        lambda value: value["detailed_ledger"]["markouts"][0].update(execution_id=99),
        lambda value: value["detailed_ledger"]["markouts"][1].update(execution_id=1),
        lambda value: value["detailed_ledger"]["markouts"][0].update(markout_time_ns=201),
        lambda value: value["detailed_episode"].update(adverse_selection=[]),
        lambda value: value["detailed_episode"].update(actions={}),
        lambda value: value["detailed_episode"].update(cancel_to_submit_ratio=0),
        lambda value: value["detailed_episode"].update(events_per_second=1),
        lambda value: value["detailed_episode"]["controller_latency"].update(count=0),
        lambda value: value["detailed_episode"]["action_dispatch_latency"].update(count=0),
        lambda value: value["detailed_episode"]["observation_staleness"].update(mean_ns=999),
        lambda value: value["detailed_episode"]["inference_latency"].update(p95_ns=999),
    ],
)
def test_independent_ledger_tampering_is_rejected(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    manifest = copy_fixture(tmp_path)
    report = manifest.parent / "report.json"
    rewrite_json(report, mutation)
    rehash_report(manifest)
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["aggregate"].update(mean_bps=0),
        lambda value: value["aggregate"].update(sample_variance_bps2=0),
        lambda value: value["aggregate"].update(median_bps=0),
        lambda value: value["aggregate"].update(var95_bps=0),
        lambda value: value["aggregate"].update(cvar95_bps=0),
        lambda value: value["aggregate"].update(var99_bps=0),
        lambda value: value["aggregate"].update(cvar99_bps=0),
        lambda value: value["aggregate"].update(quantile_method="linear"),
        lambda value: value["aggregate"].update(cvar_method="tail_rows"),
        lambda value: value["tail_episodes"][0].update(episode_id="tail-1"),
        lambda value: value["tail_episodes"][0].update(implementation_shortfall_bps="bad"),
        lambda value: value["tail_episodes"][0].update(terminal_fraction=2),
    ],
)
def test_aggregate_tampering_is_rejected(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None]
) -> None:
    manifest = copy_fixture(tmp_path)
    report = manifest.parent / "report.json"
    rewrite_json(report, mutation)
    rehash_report(manifest)
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


@pytest.mark.parametrize("relative", ["report.json", "episode-metrics.csv", "inventory-trajectory.csv", "tail-risk.csv"])
def test_unrehash_artifact_tampering_is_rejected(tmp_path: Path, relative: str) -> None:
    manifest = copy_fixture(tmp_path)
    path = manifest.parent / relative
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


def test_episode_csv_semantic_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = copy_fixture(tmp_path)
    path = manifest.parent / "episode-metrics.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(",83,", ",84,"), encoding="utf-8")
    rehash_artifact(manifest, "episode-metrics.csv")
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


def test_inventory_csv_semantic_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = copy_fixture(tmp_path)
    path = manifest.parent / "inventory-trajectory.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    rehash_artifact(manifest, "inventory-trajectory.csv")
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


def test_tail_csv_semantic_tampering_is_rejected(tmp_path: Path) -> None:
    manifest = copy_fixture(tmp_path)
    path = manifest.parent / "tail-risk.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    rehash_artifact(manifest, "tail-risk.csv")
    with pytest.raises(MetricsVerificationError):
        verify_metrics_evidence(manifest)


def test_metrics_verifier_primitive_failure_paths(tmp_path: Path) -> None:
    import robust_execution.metrics.verify as verifier

    not_object = tmp_path / "not-object.json"
    not_object.write_text("[]\n", encoding="utf-8")
    with pytest.raises(MetricsVerificationError, match="JSON object required"):
        verifier._load_object(not_object)

    for value in (True, 1.5, "1"):
        with pytest.raises(MetricsVerificationError, match="must be an integer"):
            verifier._require_int(value, "value")
    with pytest.raises(MetricsVerificationError, match="below its minimum"):
        verifier._require_int(0, "value", minimum=1)
    for value in (True, "1", float("inf"), float("nan")):
        with pytest.raises(MetricsVerificationError, match="finite number"):
            verifier._require_number(value, "value")


def test_metrics_verifier_exact_arithmetic_failure_paths() -> None:
    import robust_execution.metrics.verify as verifier

    unit = {
        "tick_numerator": 1,
        "tick_denominator": 1,
        "lot_numerator": 1,
        "lot_denominator": 1,
        "quote_atom_numerator": 1,
        "quote_atom_denominator": 1,
    }
    with pytest.raises(MetricsVerificationError, match="non-negative"):
        verifier._exact_notional(unit, -1, 1)
    fractional = dict(unit, tick_denominator=2)
    with pytest.raises(MetricsVerificationError, match="exactly representable"):
        verifier._exact_notional(fractional, 1, 1)
    with pytest.raises(MetricsVerificationError, match="signed quote-atom range"):
        verifier._exact_notional(unit, 2**63, 1)

    assert verifier._directional_cost("sell", 90, 100, 2) == 12
    with pytest.raises(MetricsVerificationError, match="buy or sell"):
        verifier._directional_cost("hold", 90, 100, 2)
    assert verifier._fractional_tail_mean([1.0, 2.0], 1.0) == 2.0
    assert verifier._fractional_tail_mean([1.0, 2.0, 3.0], 0.0) == 2.0
