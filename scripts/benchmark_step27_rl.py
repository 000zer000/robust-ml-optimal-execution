#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.rl.ppo import (  # noqa: E402
    ACTION_LABELS,
    STATE_FEATURES,
    canonical_json,
    greedy_policy,
    load_policy_artifact,
)


def percentile(values: list[int], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return float(ordered[index])


def main() -> None:
    output = ROOT / "data/sample/rl/step27-ppo-engineering"
    observation = np.asarray(
        [0.72, 0.55, 0.4, 0.55, 0.12, 0.2, 0.1, 0.1, 0.2, 0.1, 0.0],
        dtype=np.float32,
    )
    mask = np.ones(len(ACTION_LABELS), dtype=bool)
    results: dict[str, object] = {}
    for policy_path in sorted(output.glob("policy_seed_*.json")):
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        model = load_policy_artifact(payload)
        choose = greedy_policy(model)
        for _ in range(100):
            choose(observation, mask)
        samples: list[int] = []
        for _ in range(2000):
            begin = time.perf_counter_ns()
            choose(observation, mask)
            samples.append(time.perf_counter_ns() - begin)
        results[str(payload["seed"])] = {
            "samples": len(samples),
            "p50_ns": percentile(samples, 0.50),
            "p95_ns": percentile(samples, 0.95),
            "mean_ns": float(statistics.fmean(samples)),
        }
    benchmark = {
        "schema_version": "rl-inference-benchmark-v1",
        "step": 27,
        "status": "engineering_machine_specific_not_step30_performance_claim",
        "research_status": "synthetic_validation_only_non_research",
        "state_feature_count": len(STATE_FEATURES),
        "action_count": len(ACTION_LABELS),
        "policies": results,
    }
    path = ROOT / "results/validation/step27/inference_benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(benchmark) + "\n", encoding="utf-8")
    print(canonical_json(benchmark))


if __name__ == "__main__":
    main()
