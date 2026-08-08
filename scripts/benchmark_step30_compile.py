#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.performance.engineering import (  # noqa: E402
    PpoWrapper,
    TemporalWrapper,
    canonical_json,
    summarize_samples,
)
from robust_execution.prediction.temporal_model_artifacts import FAMILY  # noqa: E402
from robust_execution.prediction.temporal_models import (  # noqa: E402
    build_sequences,
    generate_temporal_training_rows,
    load_model_from_payloads,
    load_temporal_model_config,
    sequence_matrix,
    split_sequences,
)
from robust_execution.rl.ppo import load_policy_artifact  # noqa: E402


def measure(fn, repetitions: int = 10, iterations: int = 50) -> dict[str, object]:
    for _ in range(5):
        fn()
    samples = []
    for _ in range(repetitions):
        begin = time.perf_counter_ns()
        for _ in range(iterations):
            fn()
        samples.append((time.perf_counter_ns() - begin) / iterations)
    return summarize_samples(samples)


def temporal_model() -> tuple[torch.nn.Module, torch.Tensor]:
    config = load_temporal_model_config(
        ROOT / "configs/models/step23_temporal_deep_engineering.json"
    )
    sequences = split_sequences(
        build_sequences(generate_temporal_training_rows(config), config), config
    )["engineering_holdout"]
    model_root = ROOT / "data/sample/models/step23-temporal-deep-validation/models/5s" / FAMILY
    fitted = load_model_from_payloads(
        json.loads((model_root / "model-card.json").read_text(encoding="utf-8")),
        json.loads((model_root / "weights.json").read_text(encoding="utf-8")),
        config,
    )
    rows, _ = sequence_matrix(sequences, config, "5s")
    raw = torch.from_numpy(np.asarray(rows[:1], dtype=np.float32))
    return TemporalWrapper(fitted).eval(), raw


def ppo_model() -> tuple[torch.nn.Module, tuple[torch.Tensor, torch.Tensor]]:
    payload = json.loads(
        (ROOT / "data/sample/rl/step27-ppo-engineering/policy_seed_27.json").read_text(
            encoding="utf-8"
        )
    )
    model = PpoWrapper(load_policy_artifact(payload).eval()).eval()
    observation = torch.zeros((1, 11), dtype=torch.float32)
    observation[:, 0] = 0.72
    observation[:, 1] = 0.55
    mask = torch.ones((1, 6), dtype=torch.bool)
    return model, (observation, mask)


def main() -> None:
    torch.set_num_threads(1)
    result: dict[str, object] = {
        "torch_version": torch.__version__,
        "device": "cpu",
        "threads": 1,
        "batch": 1,
    }
    temporal, temporal_input = temporal_model()
    with torch.inference_mode():
        eager_temporal = measure(lambda: temporal(temporal_input))
        temporal_compile = torch.compile(
            temporal, backend="inductor", mode="reduce-overhead", fullgraph=False
        )
        compile_begin = time.perf_counter_ns()
        temporal_compile(temporal_input)
        temporal_compile_ns = time.perf_counter_ns() - compile_begin
        compiled_temporal = measure(lambda: temporal_compile(temporal_input))
        try:
            torch.compile(temporal, backend="inductor", fullgraph=True)(temporal_input)
            fullgraph_status = "unexpectedly_supported"
        except Exception as error:
            fullgraph_status = f"unsupported:{type(error).__name__}"
        try:
            torch.export.export(temporal, (temporal_input,))
            export_status = "captured"
        except Exception as error:
            export_status = f"failed:{type(error).__name__}"
    result["temporal_5s"] = {
        "eager": eager_temporal,
        "torch_compile_inductor_graph_breaks": compiled_temporal,
        "first_compile_and_run_ns": temporal_compile_ns,
        "fullgraph_status": fullgraph_status,
        "torch_export_status": export_status,
    }

    ppo, ppo_args = ppo_model()
    with torch.inference_mode():
        eager_ppo = measure(lambda: ppo(*ppo_args))
        compiled_ppo_model = torch.compile(
            ppo, backend="inductor", mode="reduce-overhead", fullgraph=True
        )
        compile_begin = time.perf_counter_ns()
        compiled_ppo_model(*ppo_args)
        ppo_compile_ns = time.perf_counter_ns() - compile_begin
        compiled_ppo = measure(lambda: compiled_ppo_model(*ppo_args))
        if not torch.equal(ppo(*ppo_args), compiled_ppo_model(*ppo_args)):
            raise SystemExit("compiled PPO changed decision")
    result["ppo_seed_27"] = {
        "eager": eager_ppo,
        "torch_compile_inductor_fullgraph": compiled_ppo,
        "first_compile_and_run_ns": ppo_compile_ns,
    }
    output = ROOT / "results/validation/step30/raw/compiled_inference.json"
    output.write_text(canonical_json(result) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
