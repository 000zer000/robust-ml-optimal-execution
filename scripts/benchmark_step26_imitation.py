from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from native_executable import native_executable
from robust_execution.imitation.learning import _episode_paths, _reconstruct_model, _state_row

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("data/sample/imitation/step26-imitation-validation/policy.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/validation/step26/inference_benchmark.json"),
    )
    args = parser.parse_args()
    oracle = args.oracle or native_executable(ROOT, "robust_execution_imitation_oracle")
    model = _reconstruct_model(json.loads(args.policy.read_text(encoding="utf-8")))
    paths = _episode_paths("benchmark", 25, 6, False)
    fields = [
        "episode_id",
        "step",
        "now",
        "start",
        "deadline",
        "arrival",
        "bid",
        "ask",
        "bid_quantity",
        "ask_quantity",
        "favorable_passive_flow",
        "filled",
        "total",
        "decision_id",
        "prediction_probability",
    ]
    rows = [
        _state_row(
            str(path["episode_id"]),
            step,
            path["market"][step],
            (index * 17 + step * 13) % 100,
            6,
        )
        for index, path in enumerate(paths)
        for step in range(6)
    ]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        completed = subprocess.run(
            [str(oracle), handle.name],
            check=True,
            text=True,
            capture_output=True,
        )
    outputs = list(csv.DictReader(io.StringIO(completed.stdout)))
    teacher_ns = np.asarray([int(row["teacher_latency_ns"]) for row in outputs], dtype=np.float64)
    features = np.asarray(
        [[float(row[name]) for name in model_feature_names()] for row in outputs],
        dtype=np.float64,
    )
    student_ns = []
    for row in features:
        begin = time.perf_counter_ns()
        model.predict(row.reshape(1, -1))
        student_ns.append(time.perf_counter_ns() - begin)
    payload = {
        "schema_version": "imitation-inference-benchmark-v1",
        "step": 26,
        "status": "engineering_machine_specific_not_step30_performance_claim",
        "rows": len(outputs),
        "teacher_cpp_shared_mpc": {
            "p50_ns": float(np.percentile(teacher_ns, 50)),
            "p95_ns": float(np.percentile(teacher_ns, 95)),
        },
        "student_numpy_batch_one": {
            "p50_ns": float(np.percentile(student_ns, 50)),
            "p95_ns": float(np.percentile(student_ns, 95)),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))


def model_feature_names() -> tuple[str, ...]:
    from robust_execution.imitation.learning import FEATURES

    return FEATURES


if __name__ == "__main__":
    main()
