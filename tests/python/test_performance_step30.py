from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import torch

from robust_execution.performance import engineering as perf

ROOT = Path(__file__).resolve().parents[2]


def tiny_config() -> perf.PerformanceConfig:
    return perf.PerformanceConfig(
        schema_version="performance-engineering-config-v1",
        step=30,
        research_status="engineering_machine_specific_non_research",
        warmup_repetitions=1,
        timing_repetitions=1,
        iterations_per_repetition=1,
        batch_sizes=(1,),
        cpu_threads=(1,),
        cpp_pairs=10,
        cpp_threads=(1,),
        latency_injection_intervals_us=(25.0, 100.0),
    )


def test_config_and_sample_summary_contract(tmp_path: Path) -> None:
    config = perf.load_config(ROOT / "configs/performance/step30_performance_engineering.json")
    assert config.step == 30
    assert perf.summarize_samples([10.0, 20.0, 30.0])["median_ns"] == 20.0
    with pytest.raises(perf.PerformanceError):
        perf.summarize_samples([])
    with pytest.raises(perf.PerformanceError):
        perf.summarize_samples([0.0])
    bad = json.loads((ROOT / "configs/performance/step30_performance_engineering.json").read_text())
    bad["step"] = 29
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(perf.PerformanceError):
        perf.load_config(path)


def test_timing_and_cpp_csv_reader(tmp_path: Path) -> None:
    timing = perf.timed_callable(lambda: 1 + 1, warmups=1, repetitions=2, iterations=2)
    assert timing["samples"] == 2
    path = tmp_path / "timing.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "repetition",
                "threads",
                "pairs",
                "operations",
                "elapsed_ns",
                "matches",
                "checksum",
            ],
        )
        writer.writeheader()
        for index, elapsed in enumerate((1000, 1200, 1100)):
            writer.writerow(
                {
                    "repetition": index,
                    "threads": 1,
                    "pairs": 5,
                    "operations": 10,
                    "elapsed_ns": elapsed,
                    "matches": 5,
                    "checksum": 15,
                }
            )
    row = perf.read_cpp_timings(path)
    assert row["threads"] == 1
    assert row["checksum"] == "15"
    assert row["throughput_ops_per_second"] > 0
    empty = tmp_path / "empty.csv"
    empty.write_text("repetition,threads,pairs,operations,elapsed_ns,matches,checksum\n")
    with pytest.raises(perf.PerformanceError):
        perf.read_cpp_timings(empty)


def test_wrappers_and_latency_panel() -> None:
    policy = json.loads(
        (ROOT / "data/sample/imitation/step26-imitation-validation/policy.json").read_text()
    )
    wrapper = perf.ImitationTorchWrapper(policy).eval()
    rows = torch.zeros((2, len(policy["scaler_mean"])), dtype=torch.float64)
    assert wrapper(rows).shape == (2,)
    ppo_payload = json.loads(
        (ROOT / "data/sample/rl/step27-ppo-engineering/policy_seed_27.json").read_text()
    )
    ppo = perf.PpoWrapper(perf.load_policy_artifact(ppo_payload).eval()).eval()
    observation = torch.zeros((2, 11), dtype=torch.float32)
    mask = torch.ones((2, len(perf.ACTION_LABELS)), dtype=torch.bool)
    assert ppo(observation, mask).shape == (2,)
    models = {
        "temporal_5s": {"torchscript_trace_cpu": {"1": {"1": {"p95_ns": 20000}}}},
        "ppo_seed_27": {"cpu": {"1": {"1": {"torchscript_trace": {"p95_ns": 30000}}}}},
        "imitation": {"1": {"numpy": {"p95_ns": 10000}}},
    }
    panel = perf.latency_injection_panel(models, (25.0, 50.0))
    assert panel["decision_intervals"]["25us"]["ppo_trace"]["missed_full_intervals"] == 1


def test_model_benchmark_smoke() -> None:
    results = perf.benchmark_models(ROOT, tiny_config())
    assert results["temporal_5s"]["parameter_bytes"] > 0
    assert results["ppo_seed_27"]["parameter_bytes"] > 0
    assert results["imitation"]["1"]["numpy"]["median_ns"] > 0


def test_pybind_benchmark_with_fake_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class Fake:
        @staticmethod
        def diagnostic_sequence(seed: int, count: int) -> list[int]:
            value = seed
            out = []
            mask = (1 << 64) - 1
            for index in range(count):
                value = (value * 6364136223846793005 + 1442695040888963407) & mask
                out.append(value ^ index)
            return out

    monkeypatch.setattr(perf, "_load_extension", lambda _: Fake())
    result = perf.benchmark_pybind(Path("unused.so"), tiny_config())
    assert result["count"] == 16
    assert result["pybind_cpp"]["median_ns"] > 0


def test_cuda_decision_and_hardware_metadata() -> None:
    metadata = perf.hardware_metadata()
    assert metadata["logical_cpu_count"] >= 1
    decision = perf.cuda_decision()
    assert "decision" in decision
    assert isinstance(decision["torch_cuda_available"], bool)


def test_generate_report_with_benchmarks_monkeypatched(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_models = {
        "temporal_5s": {"torchscript_trace_cpu": {"1": {"1": {"p95_ns": 20000}}}},
        "ppo_seed_27": {"cpu": {"1": {"1": {"torchscript_trace": {"p95_ns": 30000}}}}},
        "imitation": {"1": {"numpy": {"p95_ns": 10000}}},
    }
    monkeypatch.setattr(perf, "benchmark_models", lambda _root, _cfg: fake_models)
    monkeypatch.setattr(perf, "hardware_metadata", lambda: {"cpu": "fake"})
    monkeypatch.setattr(
        perf,
        "cuda_decision",
        lambda: {"decision": "no_cuda_device_on_validation_machine"},
    )
    report = perf.generate_report(
        ROOT,
        ROOT / "configs/performance/step30_performance_engineering.json",
        None,
    )
    assert report["step"] == 30
    assert report["historical_execution_latency_impact"] == "blocked_gate_c"
    assert report["python_cpp_boundary"]["numeric_comparison_available"] is False
