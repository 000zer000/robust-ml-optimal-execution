#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.rl.ppo import (  # noqa: E402
    ACTION_LABELS,
    RLEngineeringError,
    generate_step27_artifacts,
    historical_zero_shot_gate,
    load_policy_artifact,
)

OUTPUT = ROOT / "data/sample/rl/step27-ppo-engineering"
REPORT = OUTPUT / "report.json"
MANIFEST = OUTPUT / "manifest.json"
CONFIG = ROOT / "configs/rl/step27_ppo_engineering.json"
BENCHMARK = ROOT / "results/validation/step27/inference_benchmark.json"
RELEASE_MANIFEST = ROOT / "STEP27_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas/rl" / name).read_text(encoding="utf-8"))


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    jsonschema.validate(report, load_schema("rl-engineering-report-v1.schema.json"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    jsonschema.validate(config, load_schema("rl-engineering-config-v1.schema.json"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jsonschema.validate(manifest, load_schema("rl-engineering-manifest-v1.schema.json"))
    if manifest["config_sha256"] != sha256(CONFIG):
        fail("Step 27 config hash mismatch")
    for name, expected in manifest["files"].items():
        path = OUTPUT / name
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 27 artifact manifest mismatch: {name}")
    if report["training_seed_count"] != 5 or len(report["seed_results"]) != 5:
        fail("Step 27 engineering seed contract changed")
    if report["no_best_seed_reporting"] is not True:
        fail("Step 27 best-seed prohibition changed")
    if report["final_rl_algorithm_selected"] is not False:
        fail("Step 27 incorrectly froze the final RL algorithm while Gate C is closed")
    for row in report["seed_results"]:
        if row["id_completion_rate"] != 1.0 or row["ood_completion_rate"] != 1.0:
            fail("Step 27 terminal completion changed")
        if row["id_invalid_action_rate"] != 0.0 or row["ood_invalid_action_rate"] != 0.0:
            fail("Step 27 policy emitted an unmasked invalid action")
    if (
        report["aggregate"]["ood_mean_cost_bps"]["mean"]
        <= report["aggregate"]["id_mean_cost_bps"]["mean"]
    ):
        fail("Step 27 OOD degradation test oracle disappeared")
    if (
        report["baselines"]["wait_noop"]["id"]["mean_cost_bps"]
        <= report["baselines"]["immediate"]["id"]["mean_cost_bps"]
    ):
        fail("Step 27 no-op sanity policy is no longer penalized by terminal economics")
    audit = report["reward_audit"]
    if audit["reward_reconstruction_abs_error"] > 1e-10:
        fail("Step 27 independent reward reconstruction failed")
    if audit["terminal_completion_enforced"] is not True:
        fail("Step 27 terminal completion guard changed")
    if report["historical_zero_shot"]["status"] != "blocked_gate_c":
        fail("Step 27 historical lock boundary changed")
    try:
        historical_zero_shot_gate(admitted_days_per_instrument=0, fine_tune_requested=False)
    except RLEngineeringError:
        pass
    else:
        fail("Step 27 historical zero-shot gate did not block Gate C")
    for seed in report["training_seeds"]:
        policy_path = OUTPUT / f"policy_seed_{seed}.json"
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        jsonschema.validate(payload, load_schema("rl-policy-artifact-v1.schema.json"))
        load_policy_artifact(payload)
        if report["policy_sha256"][str(seed)] != sha256(policy_path):
            fail(f"Step 27 policy hash mismatch for seed {seed}")
        if tuple(payload["action_labels"]) != ACTION_LABELS:
            fail("Step 27 finite action order changed")
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    jsonschema.validate(benchmark, load_schema("rl-inference-benchmark-v1.schema.json"))
    if benchmark["status"] != "engineering_machine_specific_not_step30_performance_claim":
        fail("Step 27 inference benchmark claim boundary changed")
    with tempfile.TemporaryDirectory() as directory:
        rerun_root = Path(directory) / "repo"
        (rerun_root / "configs/rl").mkdir(parents=True)
        shutil.copy2(CONFIG, rerun_root / "configs/rl/step27_ppo_engineering.json")
        generate_step27_artifacts(rerun_root)
        rerun_output = rerun_root / "data/sample/rl/step27-ppo-engineering"
        if (rerun_output / "report.json").read_bytes() != REPORT.read_bytes():
            fail("Step 27 deterministic report regeneration mismatch")
        if (rerun_output / "manifest.json").read_bytes() != MANIFEST.read_bytes():
            fail("Step 27 deterministic artifact manifest regeneration mismatch")
        for seed in report["training_seeds"]:
            name = f"policy_seed_{seed}.json"
            if (rerun_output / name).read_bytes() != (OUTPUT / name).read_bytes():
                fail(f"Step 27 deterministic policy regeneration mismatch: {seed}")
    if not RELEASE_MANIFEST.is_file():
        fail("Step 27 release manifest is missing")
    release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
    if release.get("step") != 27 or release.get("research_status") != report["research_status"]:
        fail("Step 27 release manifest identity mismatch")
    for relative, expected in release.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 27 release manifest hash mismatch: {relative}")
    print(
        json.dumps(
            {
                "status": "ok",
                "step": 27,
                "training_seeds": report["training_seed_count"],
                "id_mean_cost_bps": report["aggregate"]["id_mean_cost_bps"]["mean"],
                "ood_mean_cost_bps": report["aggregate"]["ood_mean_cost_bps"]["mean"],
                "research_status": report["research_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
