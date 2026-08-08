#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema

from native_executable import native_executable
from robust_execution.analysis.prediction_decision_value import (
    ABLATIONS,
    HORIZONS,
    build_report,
    canonical_json,
    load_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/analysis/step25_prediction_decision_value_engineering.json"
REPORT = ROOT / "data/sample/analysis/step25-prediction-decision-value/report.json"
SCHEMA = ROOT / "schemas/analysis/prediction-decision-value-report-v1.schema.json"
STEP24_REPORT = ROOT / "data/sample/controller/step24-ml-mpc-validation/report.json"
MANIFEST = ROOT / "STEP25_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    config = load_config(CONFIG)
    executable = native_executable(
        ROOT,
        "robust_execution_ml_mpc_demo",
        environment="RE_STEP25_CONTROLLER_EXE",
    )
    default_controller = subprocess.check_output([str(executable)], text=True)
    if default_controller != STEP24_REPORT.read_text(encoding="utf-8"):
        fail("Step 25 weight-sweep extension changed the default Step 24 controller artifact")

    stored_text = REPORT.read_text(encoding="utf-8")
    stored = json.loads(stored_text)
    jsonschema.validate(stored, json.loads(SCHEMA.read_text(encoding="utf-8")))
    regenerated = build_report(ROOT, config, executable)
    expected_text = canonical_json(regenerated) + "\n"
    if stored_text != expected_text:
        fail("Step 25 report is not byte-identical to a clean semantic regeneration")

    payload = stored["payload"]
    canonical_payload = canonical_json(payload)
    if hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest() != stored["sha256"]:
        fail("Step 25 payload SHA-256 mismatch")
    if payload["research_status"] != "synthetic_validation_only_non_research":
        fail("Step 25 research boundary changed")
    for flag in (
        "gate_c_historical_activation",
        "primary_horizon_selected",
        "final_model_family_selected",
        "locked_research_test_opened",
        "engineering_results_used_for_research_selection",
    ):
        if payload[flag] is not False:
            fail(f"Step 25 forbidden flag activated: {flag}")

    step24 = json.loads(STEP24_REPORT.read_text(encoding="utf-8"))
    baseline = payload["decision_sensitivity"]["baseline_non_ml"]
    if baseline["actions"] != step24["payload"]["non_ml_mpc"]["actions"]:
        fail("Step 25 non-ML baseline actions drifted from Step 24")
    if (
        baseline["implementation_shortfall_bps"]
        != step24["payload"]["non_ml_mpc"]["implementation_shortfall_bps"]
    ):
        fail("Step 25 non-ML baseline accounting drifted from Step 24")

    weights = payload["decision_sensitivity"]["weight_grid_bps"]
    if weights != list(config.weight_grid_bps) or weights[0] != 0.0:
        fail("Step 25 weight grid changed")
    for horizon in HORIZONS:
        prediction = payload["prediction_analysis"][horizon]
        if prediction["rows"] != 400:
            fail(f"{horizon}: engineering holdout sequence count changed")
        oracle = prediction["metrics"]["perfect_event_oracle"]
        if oracle["log_loss"] > 1e-7 or oracle["brier"] > 1e-14:
            fail(f"{horizon}: perfect-event oracle metric sanity failed")
        horizon_sweep = payload["decision_sensitivity"]["horizons"][horizon]
        for ablation in ABLATIONS:
            sweep = horizon_sweep[ablation]["sweep"]
            if len(sweep) != len(weights):
                fail(f"{horizon}/{ablation}: incomplete controller weight sweep")
            if sweep[0]["actions"] != baseline["actions"]:
                fail(f"{horizon}/{ablation}: zero-weight controller changed baseline actions")
            if any(row["complete"] is not True for row in sweep):
                fail(f"{horizon}/{ablation}: incomplete parent order in sweep")
        if (
            horizon_sweep["training_base_rate"]["first_grid_weight_with_action_change_bps"]
            is not None
        ):
            fail(f"{horizon}: centered training-base-rate control changed actions")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "step25-manifest-v1" or manifest.get("step") != 25:
        fail("Step 25 manifest identity changed")
    for relative, expected_hash in manifest.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file():
            fail(f"Step 25 manifest file is missing: {relative}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            fail(f"Step 25 manifest hash mismatch: {relative}")

    summary = payload["engineering_summary"]
    if summary["prediction_metric_improvement_without_decision_change_observed"] is not True:
        fail("Step 25 failed to preserve prediction-improves/decision-unchanged evidence")
    if summary["prediction_metric_degradation_with_decision_change_observed"] is not True:
        fail("Step 25 failed to preserve prediction-worse/decision-changed evidence")
    if summary["perfect_label_oracle_can_worsen_execution_fixture"] is not True:
        fail("Step 25 oracle decision-mismatch negative result disappeared")
    if summary["any_changed_action_improved_implementation_shortfall_fixture"] is not False:
        fail("Step 25 fixture unexpectedly gained a decision-value win")

    print(
        json.dumps(
            {
                "status": "ok",
                "step": 25,
                "horizons": list(HORIZONS),
                "prediction_rows_per_horizon": 400,
                "weight_points": len(weights),
                "research_status": payload["research_status"],
                "negative_result_preserved": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
