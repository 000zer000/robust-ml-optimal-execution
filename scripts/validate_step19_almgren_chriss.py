#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/sample/almgren_chriss/step19-validation/report.json"
EXE = ROOT / "build/gcc-debug/robust_execution_almgren_chriss_demo"


def fail(message: str) -> None:
    raise SystemExit(message)


def expected_continuous_inventory(record: dict) -> list[float]:
    p = record["parameters"]
    n = int(p["slice_count"])
    lam = float(p["risk_aversion_lambda"])
    sigma = float(p["volatility_sigma"])
    eta = float(p["temporary_impact_eta"])
    gamma = float(p["permanent_impact_gamma"])
    time_unit = float(p["time_unit_ns"])
    start, end = 1000.0, 2000.0
    tau = ((end - start) / time_unit) / n
    eta_tilde = eta - 0.5 * gamma * tau
    alpha = (lam * sigma * sigma / eta_tilde) * tau * tau
    if alpha == 0.0:
        return [(n - j) / n for j in range(n + 1)]
    kappa = math.acosh(1.0 + 0.5 * alpha) / tau
    total_horizon = n * tau
    denominator = math.sinh(kappa * total_horizon)
    return [math.sinh(kappa * (total_horizon - j * tau)) / denominator if j < n else 0.0 for j in range(n + 1)]


def main() -> None:
    text = REPORT.read_text()
    rerun = subprocess.check_output([str(EXE)], text=True)
    if rerun != text:
        fail("Step 19 report is not byte-identical to executable output")
    obj = json.loads(text)
    payload = obj["payload"]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != obj["sha256"]:
        fail("Step 19 payload hash mismatch")
    if payload["evidence_status"] != "synthetic_validation_only_non_research":
        fail("Step 19 research boundary changed")
    if payload["model"] != "discrete_linear_almgren_chriss_zero_drift":
        fail("unexpected Almgren-Chriss model")
    if payload["risk_neutral_matches_twap"] is not True:
        fail("risk-neutral Almgren-Chriss no longer matches TWAP")

    expected = {
        "risk_neutral": ([25, 25, 25, 25], 0, 2500.0, 8750.0),
        "moderate_risk": ([51, 26, 14, 9], 37, 3554.0, 3011.0),
        "high_risk": ([73, 20, 5, 2], 68, 5758.0, 782.0),
    }
    first_slices: list[int] = []
    for name, (quantities, shortfall, expected_cost, variance) in expected.items():
        record = payload[name]
        actual = [row["quantity_lots"] for row in record["slices"]]
        if actual != quantities:
            fail(f"{name} integer allocation changed")
        if sum(actual) != 100:
            fail(f"{name} does not conserve parent quantity")
        if record["implementation_shortfall_bps"] != shortfall:
            fail(f"{name} synthetic metric oracle changed")
        if abs(float(record["expected_cost_model_units"]) - expected_cost) > 1e-9:
            fail(f"{name} model expected-cost oracle changed")
        if abs(float(record["variance_model_units"]) - variance) > 1e-9:
            fail(f"{name} model variance oracle changed")
        p = record["parameters"]
        if p["calibration_cutoff_ns"] >= 1000:
            fail(f"{name} calibration cutoff leaks into episode")
        if not p["provenance_id"]:
            fail(f"{name} calibration provenance missing")
        inv = expected_continuous_inventory(record)
        if any(inv[i] < inv[i + 1] - 1e-12 for i in range(len(inv) - 1)):
            fail(f"{name} closed-form inventory path is not monotone")
        first_slices.append(actual[0])

    if not (first_slices[0] < first_slices[1] < first_slices[2]):
        fail("risk aversion no longer monotonically front-loads the validation schedules")
    if abs(float(payload["moderate_risk"]["kappa"]) - math.log(2.0)) > 1e-12:
        fail("moderate-risk kappa no longer matches ln(2) closed-form oracle")
    if "synthetic_validation_only_non_research" not in text:
        fail("Step 19 report lost explicit non-research label")

    print(json.dumps({
        "status": "ok",
        "step": 19,
        "model": payload["model"],
        "risk_neutral_matches_twap": True,
        "front_loading_monotone": True,
        "research_status": payload["evidence_status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
