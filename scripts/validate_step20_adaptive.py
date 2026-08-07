#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/sample/adaptive/step20-validation/report.json"
CONFIG = ROOT / "configs/strategies/step20_non_ml_adaptive.json"
EXE = ROOT / "build/gcc-debug/robust_execution_adaptive_demo"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    text = REPORT.read_text()
    rerun = subprocess.check_output([str(EXE)], text=True)
    if rerun != text:
        fail("Step 20 report is not byte-identical to executable output")
    obj = json.loads(text)
    payload = obj["payload"]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != obj["sha256"]:
        fail("Step 20 payload hash mismatch")
    if payload["evidence_status"] != "synthetic_validation_only_non_research":
        fail("Step 20 research boundary changed")
    if payload["gate_d_status"] != "engineering_pass_research_activation_requires_gate_c":
        fail("Step 20 Gate D boundary changed")
    if payload["historical_exact_queue_used"] is not False:
        fail("Step 20 must not use exact historical queue position")
    if payload["ml_or_learned_signal_used"] is not False:
        fail("Step 20 must remain non-ML")
    if payload["calibration_cutoff_ns"] >= 1000 or not payload["calibration_provenance"]:
        fail("Step 20 calibration provenance/cutoff invalid")
    if payload["mpc_early_oracle"]["mode"] != "passive":
        fail("Step 20 early MPC oracle changed")
    if payload["mpc_late_oracle"]["mode"] != "aggressive":
        fail("Step 20 late MPC oracle changed")
    if payload["mpc_early_oracle"]["nodes"] <= 10:
        fail("Step 20 MPC no longer performs a multi-step search")
    for name in ("queue_aware_heuristic", "non_ml_mpc"):
        record = payload[name]
        if record["complete"] is not True:
            fail(f"{name} synthetic accounting fixture is incomplete")
        if not record["actions"]:
            fail(f"{name} has no validation actions")
    config = json.loads(CONFIG.read_text())
    if config["research_status"] != "synthetic_validation_parameters_only":
        fail("Step 20 config lost synthetic-only status")
    if config["calibration"]["cutoff_ns"] >= 1000:
        fail("Step 20 config calibration cutoff leaks into episode")
    if config["non_ml_mpc"]["maximum_passive_fraction"] != "1/2":
        fail("Step 20 passive participation cap changed")
    if "1/1" not in config["non_ml_mpc"]["action_fractions"]:
        fail("Step 20 MPC lost full-residual aggressive action capability")
    print(json.dumps({
        "status": "ok",
        "step": 20,
        "gate_d": payload["gate_d_status"],
        "heuristic": True,
        "mpc": True,
        "research_status": payload["evidence_status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
