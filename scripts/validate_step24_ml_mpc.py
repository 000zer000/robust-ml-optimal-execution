#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import math
import subprocess
from pathlib import Path

import jsonschema

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/sample/controller/step24-ml-mpc-validation"
REPORT = OUT / "report.json"
TAPE = OUT / "prediction-tapes.json"
CONFIG = ROOT / "configs/strategies/step24_ml_mpc_engineering.json"
REPORT_SCHEMA = ROOT / "schemas/controller/ml-mpc-controller-report-v1.schema.json"
TAPE_SCHEMA = ROOT / "schemas/controller/ml-mpc-prediction-tape-v1.schema.json"
EXE = native_executable(ROOT, "robust_execution_ml_mpc_demo")
MODELS = ROOT / "data/sample/models/step23-temporal-deep-validation/models"
STEP23_REPORT = ROOT / "data/sample/models/step23-temporal-deep-validation/report.json"
HORIZONS = ("250ms", "1s", "5s")


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_payload(payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def load_columns(horizon: str) -> dict[str, list[object]]:
    path = (
        MODELS
        / horizon
        / "causal_conv1d_lstm/tables/engineering_holdout_predictions/columns.json.gz"
    )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)["columns"]


def diagnostic_probability(diagnostic: str) -> float:
    fields = diagnostic.split("|")
    marker = fields.index(next(item for item in fields if item.startswith("prediction=")))
    return float(fields[marker + 1])


def validate_source_linkage(report: dict[str, object], tape: dict[str, object]) -> None:
    step23 = json.loads(STEP23_REPORT.read_text())
    source_ids = report["payload"]["source_endpoint_row_ids"]
    for horizon in HORIZONS:
        columns = load_columns(horizon)
        card = json.loads((MODELS / horizon / "causal_conv1d_lstm/model-card.json").read_text())
        horizon_report = report["payload"]["horizons"][horizon]
        horizon_tape = tape["horizons"][horizon]
        expected_hash = step23["models"][horizon]["prediction_data_sha256"]
        if horizon_report["prediction_table_sha256"] != expected_hash:
            fail(f"{horizon}: controller report does not reference Step 23 prediction artifact")
        if horizon_tape["prediction_table_sha256"] != expected_hash:
            fail(f"{horizon}: prediction tape hash does not match Step 23")
        if not math.isclose(
            horizon_tape["training_base_rate"], card["training_prevalence"], rel_tol=0, abs_tol=0
        ):
            fail(f"{horizon}: training base rate changed")
        if source_ids != columns["endpoint_row_id"][:4]:
            fail(f"{horizon}: source endpoint rows changed")
        for index, record in enumerate(horizon_tape["records"]):
            if record["endpoint_row_id"] != columns["endpoint_row_id"][index]:
                fail(f"{horizon}: prediction tape endpoint mismatch")
            if record["calibrated_probability"] != columns["calibrated_probability"][index]:
                fail(f"{horizon}: calibrated probability changed")
            if record["uncalibrated_probability"] != columns["uncalibrated_probability"][index]:
                fail(f"{horizon}: uncalibrated probability changed")
            if record["target"] != columns["target"][index]:
                fail(f"{horizon}: oracle target changed")
            if record["feature_cutoff_time_ns"] > record["endpoint_time_ns"]:
                fail(f"{horizon}: feature cutoff is noncausal")
            if record["available_time_ns"] > record["endpoint_time_ns"]:
                fail(f"{horizon}: prediction availability is noncausal")

        calibrated = horizon_report["calibrated"]["diagnostics"]
        if len(calibrated) != 4:
            fail(f"{horizon}: calibrated diagnostic count changed")
        for index, diagnostic in enumerate(calibrated):
            if not math.isclose(
                diagnostic_probability(diagnostic),
                columns["calibrated_probability"][index],
                rel_tol=0,
                abs_tol=5e-13,
            ):
                fail(f"{horizon}: C++ controller probability does not match Step 23 artifact")


def validate_ablations(report: dict[str, object]) -> None:
    payload = report["payload"]
    non_ml = payload["non_ml_mpc"]
    oracle_changed = False
    for horizon in HORIZONS:
        record = payload["horizons"][horizon]
        for name in (
            "calibrated",
            "training_base_rate_ablation",
            "shuffled_within_day_instrument_ablation",
            "stale_ablation",
            "uncalibrated_ablation",
            "perfect_event_oracle_ablation",
            "prediction_weight_zero_ablation",
        ):
            if record[name]["complete"] is not True:
                fail(f"{horizon}/{name}: controller did not complete parent order")
        for neutral in ("training_base_rate_ablation", "prediction_weight_zero_ablation"):
            if record[neutral]["actions"] != non_ml["actions"]:
                fail(f"{horizon}/{neutral}: neutral ablation changed actions")
            if (
                record[neutral]["implementation_shortfall_bps"]
                != non_ml["implementation_shortfall_bps"]
            ):
                fail(f"{horizon}/{neutral}: neutral ablation changed accounting")
        if record["perfect_event_oracle_ablation"]["actions"] != non_ml["actions"]:
            oracle_changed = True
    if not oracle_changed:
        fail("oracle ablation never changes a controller decision; integration may be inert")


def main() -> None:
    report_text = REPORT.read_text()
    rerun = subprocess.check_output([str(EXE)], text=True)
    if rerun != report_text:
        fail("Step 24 report is not byte-identical to executable output")
    report = json.loads(report_text)
    tape = json.loads(TAPE.read_text())
    config = json.loads(CONFIG.read_text())
    jsonschema.validate(report, json.loads(REPORT_SCHEMA.read_text()))
    jsonschema.validate(tape, json.loads(TAPE_SCHEMA.read_text()))

    canonical = canonical_payload(report["payload"])
    if hashlib.sha256(canonical.encode()).hexdigest() != report["sha256"]:
        fail("Step 24 report payload hash mismatch")
    if report["payload"]["evidence_status"] != "synthetic_validation_only_non_research":
        fail("Step 24 research boundary changed")
    if report["payload"]["gate_c_historical_activation"] is not False:
        fail("Step 24 improperly activated historical research")
    if report["payload"]["final_horizon_selected"] is not False:
        fail("Step 24 selected a final horizon")
    if report["payload"]["final_model_family_selected"] is not False:
        fail("Step 24 selected a final model family")
    if report["payload"]["locked_research_test_opened"] is not False:
        fail("Step 24 opened the locked research test")
    if config["fairness_contract"]["same_solver"] is not True:
        fail("Step 24 config lost the shared-solver fairness requirement")
    if (
        config["prediction_risk_weight_status"]
        != "synthetic_engineering_fixture_not_research_tuned"
    ):
        fail("Step 24 synthetic controller weight was mislabelled")

    validate_source_linkage(report, tape)
    validate_ablations(report)
    print(
        json.dumps(
            {
                "status": "ok",
                "step": 24,
                "shared_solver": True,
                "horizons": list(HORIZONS),
                "required_ablations": 6,
                "research_status": report["payload"]["evidence_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
