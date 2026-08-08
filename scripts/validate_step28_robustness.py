#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.robustness.matrix import generate_step28_artifacts  # noqa: E402

OUTPUT = ROOT / "data/sample/robustness/step28-engineering-matrix"
REPORT = OUTPUT / "report.json"
MANIFEST = OUTPUT / "manifest.json"
CONFIG = ROOT / "configs/robustness/step28_robustness_engineering.json"
RELEASE_MANIFEST = ROOT / "evidence/validation-ledger/STEP28_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas/robustness" / name).read_text(encoding="utf-8"))


def copy_dependency(source: Path, target_root: Path) -> None:
    relative = source.relative_to(ROOT)
    destination = target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema("robustness-engineering-report-v1.schema.json"))
    jsonschema.validate(config, schema("robustness-engineering-config-v1.schema.json"))
    jsonschema.validate(manifest, schema("robustness-engineering-manifest-v1.schema.json"))
    if manifest["config_sha256"] != sha256(CONFIG):
        fail("Step 28 config hash mismatch")
    for name, expected in manifest["files"].items():
        path = OUTPUT / name
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 28 artifact hash mismatch: {name}")
    if report["interactive_case_count"] != 43:
        fail("Step 28 interactive matrix size changed")
    if report["paired_episode_count_per_cell"] != 24:
        fail("Step 28 paired episode contract changed")
    if report["historical_cells"]["locked_test_opened"] is not False:
        fail("Step 28 opened the locked historical test")
    if report["historical_cells"]["status"] != "blocked_gate_c":
        fail("Step 28 historical Gate C boundary changed")
    if report["statistics_boundary"]["deferred_to_step29"] is not True:
        fail("Step 28 crossed the Step 29 statistics boundary")
    if report["performance_boundary"]["deferred_to_step30"] is not True:
        fail("Step 28 crossed the Step 30 performance boundary")
    summary = report["ranking_summary"]
    if summary["rank_switch_case_count"] <= 0:
        fail("Step 28 rank-switch test oracle disappeared")
    if summary["win_counts"]["liquidity_aware"] <= summary["win_counts"]["ppo_aggregate"]:
        fail("Step 28 negative result was unexpectedly inverted")
    required_modes = {
        "calibrated_model",
        "uncalibrated_model",
        "stale",
        "training_base_rate",
        "shuffled_within_day_instrument",
    }
    if set(report["prediction_panel"]["required_modes_covered"]) != required_modes:
        fail("Step 28 prediction degradation coverage changed")
    if report["compute_panel"]["formal_performance_claim_deferred_to_step30"] is not True:
        fail("Step 28 compute panel promoted an engineering benchmark")
    for case_metrics in report["interactive_metrics"].values():
        for metrics in case_metrics.values():
            if metrics["completion_rate"] != 1.0 or metrics["invalid_action_rate"] != 0.0:
                fail("Step 28 common completion/action contract changed")
    dependencies = [
        CONFIG,
        ROOT / "configs/rl/step27_ppo_engineering.json",
        ROOT / "data/sample/analysis/step25-prediction-decision-value/report.json",
        ROOT / "data/sample/queue_models/step16-queue-model-validation/report.json",
        ROOT / "results/validation/step23/inference_benchmark.json",
        ROOT / "results/validation/step26/inference_benchmark.json",
        ROOT / "results/validation/step27/inference_benchmark.json",
    ]
    dependencies.extend(
        ROOT / f"data/sample/rl/step27-ppo-engineering/policy_seed_{seed}.json"
        for seed in (27, 127, 227, 327, 427)
    )
    with tempfile.TemporaryDirectory() as directory:
        rerun_root = Path(directory) / "repo"
        for path in dependencies:
            copy_dependency(path, rerun_root)
        generate_step28_artifacts(rerun_root)
        rerun = rerun_root / "data/sample/robustness/step28-engineering-matrix"
        for name in (
            "report.json",
            "stress-results.csv",
            "ranking-stability.json",
            "manifest.json",
        ):
            if (rerun / name).read_bytes() != (OUTPUT / name).read_bytes():
                fail(f"Step 28 deterministic regeneration mismatch: {name}")
    if not RELEASE_MANIFEST.is_file():
        fail("Step 28 release manifest is missing")
    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    if release.get("step") != 28 or release.get("research_status") != report["research_status"]:
        fail("Step 28 release manifest identity mismatch")
    for relative, expected in release.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 28 release manifest hash mismatch: {relative}")
    print(
        json.dumps(
            {
                "status": "ok",
                "step": 28,
                "interactive_cases": report["interactive_case_count"],
                "rank_switches": summary["rank_switch_case_count"],
                "research_status": report["research_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
