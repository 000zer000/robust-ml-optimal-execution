"""Performance engineering utilities for Step 30.

Timing artifacts are machine-specific evidence. Scientific model/strategy artifacts remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import statistics
import time
from typing import Callable, Iterable

import numpy as np
import psutil
import torch
from torch import nn
from threadpoolctl import threadpool_limits

from robust_execution.imitation.learning import _reconstruct_model
from robust_execution.prediction.temporal_model_artifacts import FAMILY
from robust_execution.prediction.temporal_models import (
    build_sequences,
    generate_temporal_training_rows,
    load_model_from_payloads,
    load_temporal_model_config,
    sequence_matrix,
    split_sequences,
)
from robust_execution.rl.ppo import ACTION_LABELS, load_policy_artifact


class PerformanceError(ValueError):
    """Raised when the Step 30 performance contract is violated."""


@dataclass(frozen=True)
class PerformanceConfig:
    schema_version: str
    step: int
    research_status: str
    warmup_repetitions: int
    timing_repetitions: int
    iterations_per_repetition: int
    batch_sizes: tuple[int, ...]
    cpu_threads: tuple[int, ...]
    cpp_pairs: int
    cpp_threads: tuple[int, ...]
    latency_injection_intervals_us: tuple[float, ...]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path) -> PerformanceConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    config = PerformanceConfig(
        schema_version=str(raw["schema_version"]),
        step=int(raw["step"]),
        research_status=str(raw["research_status"]),
        warmup_repetitions=int(raw["warmup_repetitions"]),
        timing_repetitions=int(raw["timing_repetitions"]),
        iterations_per_repetition=int(raw["iterations_per_repetition"]),
        batch_sizes=tuple(int(v) for v in raw["batch_sizes"]),
        cpu_threads=tuple(int(v) for v in raw["cpu_threads"]),
        cpp_pairs=int(raw["cpp_pairs"]),
        cpp_threads=tuple(int(v) for v in raw["cpp_threads"]),
        latency_injection_intervals_us=tuple(
            float(v) for v in raw["latency_injection_intervals_us"]
        ),
    )
    if config.schema_version != "performance-engineering-config-v1" or config.step != 30:
        raise PerformanceError("Step 30 config identity changed")
    if config.research_status != "engineering_machine_specific_non_research":
        raise PerformanceError("Step 30 research boundary changed")
    if config.timing_repetitions < 5 or config.warmup_repetitions < 1:
        raise PerformanceError("Step 30 requires warm-up and at least five timed repetitions")
    if config.iterations_per_repetition < 1:
        raise PerformanceError("iterations_per_repetition must be positive")
    for values, name in (
        (config.batch_sizes, "batch_sizes"),
        (config.cpu_threads, "cpu_threads"),
        (config.cpp_threads, "cpp_threads"),
    ):
        if not values or tuple(sorted(set(values))) != values or values[0] <= 0:
            raise PerformanceError(f"{name} must be sorted unique positive values")
    if config.cpp_pairs < 1 or any(v <= 0 for v in config.latency_injection_intervals_us):
        raise PerformanceError("invalid workload size or latency injection interval")
    return config


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise PerformanceError("cannot summarize empty timing samples")
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def summarize_samples(values: Iterable[float]) -> dict[str, float | int | list[float]]:
    samples = [float(v) for v in values]
    if not samples or any(not math.isfinite(v) or v <= 0 for v in samples):
        raise PerformanceError("timing samples must be finite and positive")
    median = float(statistics.median(samples))
    return {
        "samples": len(samples),
        "raw_ns": samples,
        "median_ns": median,
        "p95_ns": percentile(samples, 95),
        "mean_ns": float(statistics.fmean(samples)),
        "mad_ns": float(statistics.median(abs(v - median) for v in samples)),
        "min_ns": float(min(samples)),
        "max_ns": float(max(samples)),
    }


def timed_callable(
    function: Callable[[], object], *, warmups: int, repetitions: int, iterations: int
) -> dict[str, float | int | list[float]]:
    for _ in range(warmups):
        function()
    samples: list[float] = []
    for _ in range(repetitions):
        begin = time.perf_counter_ns()
        for _ in range(iterations):
            function()
        elapsed = time.perf_counter_ns() - begin
        samples.append(elapsed / iterations)
    return summarize_samples(samples)


def read_cpp_timings(path: Path) -> dict[str, object]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        raise PerformanceError(f"empty C++ timing file: {path}")
    elapsed = [float(row["elapsed_ns"]) for row in rows]
    operations = int(rows[0]["operations"])
    summary = summarize_samples(elapsed)
    median_s = float(summary["median_ns"]) / 1e9
    return {
        "threads": int(rows[0]["threads"]),
        "pairs": int(rows[0]["pairs"]),
        "operations": operations,
        "throughput_ops_per_second": operations / median_s,
        "timing": summary,
        "checksum": str(rows[0]["checksum"]),
        "sha256": sha256_path(path),
    }


class TemporalWrapper(nn.Module):
    def __init__(self, fitted: object) -> None:
        super().__init__()
        self.network = fitted.network  # type: ignore[attr-defined]
        self.register_buffer(
            "mean", torch.tensor(fitted.scaler.mean, dtype=torch.float32)
        )  # type: ignore[attr-defined]
        self.register_buffer(
            "scale", torch.tensor(fitted.scaler.scale, dtype=torch.float32)
        )  # type: ignore[attr-defined]
        self.intercept = float(fitted.calibrator.intercept)  # type: ignore[attr-defined]
        self.slope = float(fitted.calibrator.slope)  # type: ignore[attr-defined]

    def forward(self, raw: torch.Tensor) -> torch.Tensor:
        standardized = (raw - self.mean) / self.scale
        logits = torch.clamp(self.network(standardized), -40.0, 40.0)
        calibrated_logits = torch.clamp(self.intercept + self.slope * logits, -40.0, 40.0)
        return torch.sigmoid(calibrated_logits)


class PpoWrapper(nn.Module):
    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, observation: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        logits, _ = self.model(observation)
        masked = logits.masked_fill(~mask, -1.0e9)
        return torch.argmax(masked, dim=-1)


class ImitationTorchWrapper(nn.Module):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__()
        mean = torch.tensor(payload["scaler_mean"], dtype=torch.float64)
        scale = torch.tensor(payload["scaler_scale"], dtype=torch.float64)
        coefs = payload["coefs"]
        intercepts = payload["intercepts"]
        self.register_buffer("mean", mean)
        self.register_buffer("scale", scale)
        self.register_buffer(
            "w0", torch.tensor(coefs[0], dtype=torch.float64)
        )  # type: ignore[index]
        self.register_buffer(
            "w1", torch.tensor(coefs[1], dtype=torch.float64)
        )  # type: ignore[index]
        self.register_buffer(
            "b0", torch.tensor(intercepts[0], dtype=torch.float64)
        )  # type: ignore[index]
        self.register_buffer(
            "b1", torch.tensor(intercepts[1], dtype=torch.float64)
        )  # type: ignore[index]

    def forward(self, raw: torch.Tensor) -> torch.Tensor:
        z = (raw - self.mean) / self.scale
        hidden = torch.relu(z @ self.w0 + self.b0)
        logits = hidden @ self.w1 + self.b1
        return torch.argmax(logits, dim=-1)


def _bench_torch(
    module: nn.Module,
    args: tuple[torch.Tensor, ...],
    config: PerformanceConfig,
) -> dict[str, object]:
    module.eval()
    with torch.inference_mode():
        result = timed_callable(
            lambda: module(*args),
            warmups=config.warmup_repetitions,
            repetitions=config.timing_repetitions,
            iterations=config.iterations_per_repetition,
        )
    return result


def _load_extension(path: Path) -> object:
    spec = importlib.util.spec_from_file_location("_core", path)
    if spec is None or spec.loader is None:
        raise PerformanceError("cannot load pybind extension")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cpu_model_name() -> str:
    path = Path("/proc/cpuinfo")
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def _command_version(command: str) -> str:
    executable = shutil.which(command)
    if executable is None:
        return "unavailable"
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    first = (completed.stdout or completed.stderr).splitlines()
    return first[0].strip() if first else "unknown"


def hardware_metadata() -> dict[str, object]:
    process = psutil.Process()
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": _cpu_model_name(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "memory_bytes": psutil.virtual_memory().total,
        "process_affinity": process.cpu_affinity() if hasattr(process, "cpu_affinity") else [],
        "cxx_compiler": _command_version("c++"),
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "scikit_learn_version": importlib.metadata.version("scikit-learn"),
        "torch_num_threads_initial": torch.get_num_threads(),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
        "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
    }


def benchmark_models(root: Path, config: PerformanceConfig) -> dict[str, object]:
    results: dict[str, object] = {}

    temporal_config = load_temporal_model_config(
        root / "configs/models/step23_temporal_deep_engineering.json"
    )
    sequences = split_sequences(
        build_sequences(generate_temporal_training_rows(temporal_config), temporal_config),
        temporal_config,
    )["engineering_holdout"]
    temporal_root = root / "data/sample/models/step23-temporal-deep-validation/models/5s" / FAMILY
    fitted = load_model_from_payloads(
        json.loads((temporal_root / "model-card.json").read_text(encoding="utf-8")),
        json.loads((temporal_root / "weights.json").read_text(encoding="utf-8")),
        temporal_config,
    )
    temporal = TemporalWrapper(fitted).eval()
    temporal_rows, _ = sequence_matrix(sequences, temporal_config, "5s")
    temporal_eager: dict[str, object] = {}
    temporal_traced: dict[str, object] = {}
    for threads in config.cpu_threads:
        torch.set_num_threads(threads)
        per_eager: dict[str, object] = {}
        per_trace: dict[str, object] = {}
        for batch in config.batch_sizes:
            raw = torch.from_numpy(np.asarray(temporal_rows[:batch], dtype=np.float32))
            if raw.shape[0] < batch:
                repeats = int(math.ceil(batch / raw.shape[0]))
                raw = raw.repeat((repeats, 1, 1))[:batch]
            traced = torch.jit.trace(temporal, raw, check_trace=True)
            eager_out = temporal(raw)
            trace_out = traced(raw)
            if not torch.allclose(eager_out, trace_out, atol=1e-6, rtol=1e-6):
                raise PerformanceError("temporal traced inference changed predictions")
            eager = _bench_torch(temporal, (raw,), config)
            compiled = _bench_torch(traced, (raw,), config)
            eager["throughput_rows_per_second"] = batch / (float(eager["median_ns"]) / 1e9)
            compiled["throughput_rows_per_second"] = batch / (float(compiled["median_ns"]) / 1e9)
            per_eager[str(batch)] = eager
            per_trace[str(batch)] = compiled
        temporal_eager[str(threads)] = per_eager
        temporal_traced[str(threads)] = per_trace
    results["temporal_5s"] = {
        "eager_cpu": temporal_eager,
        "torchscript_trace_cpu": temporal_traced,
        "torch_compile_fullgraph": {
            "status": "unsupported_lstm_fullgraph_in_current_torch",
            "attempted": True,
        },
        "parameter_bytes": sum(p.numel() * p.element_size() for p in temporal.parameters()),
    }

    ppo_payload = json.loads(
        (root / "data/sample/rl/step27-ppo-engineering/policy_seed_27.json").read_text(
            encoding="utf-8"
        )
    )
    ppo = PpoWrapper(load_policy_artifact(ppo_payload).eval()).eval()
    ppo_results: dict[str, object] = {}
    for threads in config.cpu_threads:
        torch.set_num_threads(threads)
        rows: dict[str, object] = {}
        for batch in config.batch_sizes:
            obs = torch.zeros((batch, 11), dtype=torch.float32)
            obs[:, 0] = 0.72
            obs[:, 1] = 0.55
            mask = torch.ones((batch, len(ACTION_LABELS)), dtype=torch.bool)
            traced = torch.jit.trace(ppo, (obs, mask), check_trace=True)
            if not torch.equal(ppo(obs, mask), traced(obs, mask)):
                raise PerformanceError("PPO traced inference changed decisions")
            eager = _bench_torch(ppo, (obs, mask), config)
            compiled = _bench_torch(traced, (obs, mask), config)
            eager["throughput_rows_per_second"] = batch / (float(eager["median_ns"]) / 1e9)
            compiled["throughput_rows_per_second"] = batch / (float(compiled["median_ns"]) / 1e9)
            rows[str(batch)] = {"eager": eager, "torchscript_trace": compiled}
        ppo_results[str(threads)] = rows
    results["ppo_seed_27"] = {
        "cpu": ppo_results,
        "parameter_bytes": sum(p.numel() * p.element_size() for p in ppo.parameters()),
    }

    imitation_payload = json.loads(
        (root / "data/sample/imitation/step26-imitation-validation/policy.json").read_text(
            encoding="utf-8"
        )
    )
    imitation_numpy = _reconstruct_model(imitation_payload)
    imitation_torch = ImitationTorchWrapper(imitation_payload).eval()
    imitation_results: dict[str, object] = {}
    for batch in config.batch_sizes:
        raw_np = np.zeros((batch, len(imitation_numpy.scaler_mean)), dtype=np.float64)
        raw_t = torch.from_numpy(raw_np)
        expected = imitation_numpy.predict(raw_np)[0]
        class_index = np.asarray([imitation_numpy.classes.index(str(v)) for v in expected])
        traced = torch.jit.trace(imitation_torch, raw_t, check_trace=True)
        actual = traced(raw_t).detach().cpu().numpy()
        if not np.array_equal(class_index, actual):
            raise PerformanceError("imitation traced inference changed decisions")
        with threadpool_limits(limits=1):
            numpy_timing = timed_callable(
                lambda: imitation_numpy.predict(raw_np),
                warmups=config.warmup_repetitions,
                repetitions=config.timing_repetitions,
                iterations=config.iterations_per_repetition,
            )
        torch.set_num_threads(1)
        traced_timing = _bench_torch(traced, (raw_t,), config)
        for row in (numpy_timing, traced_timing):
            row["throughput_rows_per_second"] = batch / (float(row["median_ns"]) / 1e9)
        imitation_results[str(batch)] = {
            "numpy": numpy_timing,
            "torchscript_trace": traced_timing,
        }
    results["imitation"] = imitation_results
    return results


def benchmark_pybind(extension_path: Path, config: PerformanceConfig) -> dict[str, object]:
    module = _load_extension(extension_path)
    seed = 17
    count = 16

    def python_sequence() -> list[int]:
        value = seed
        result = []
        mask = (1 << 64) - 1
        for index in range(count):
            value = (value * 6364136223846793005 + 1442695040888963407) & mask
            result.append(value ^ index)
        return result

    expected = python_sequence()
    if list(module.diagnostic_sequence(seed, count)) != expected:
        raise PerformanceError("Python/C++ boundary diagnostic changed semantics")
    cpp = timed_callable(
        lambda: module.diagnostic_sequence(seed, count),
        warmups=config.warmup_repetitions,
        repetitions=config.timing_repetitions,
        iterations=config.iterations_per_repetition,
    )
    py = timed_callable(
        python_sequence,
        warmups=config.warmup_repetitions,
        repetitions=config.timing_repetitions,
        iterations=config.iterations_per_repetition,
    )
    return {"pybind_cpp": cpp, "pure_python": py, "count": count}


def latency_injection_panel(
    model_results: dict[str, object], intervals_us: tuple[float, ...]
) -> dict[str, object]:
    temporal = model_results["temporal_5s"]["torchscript_trace_cpu"]["1"][
        "1"
    ]  # type: ignore[index]
    ppo = model_results["ppo_seed_27"]["cpu"]["1"]["1"][
        "torchscript_trace"
    ]  # type: ignore[index]
    imitation = model_results["imitation"]["1"]["numpy"]  # type: ignore[index]
    p95_us = {
        "temporal_5s_trace": float(temporal["p95_ns"]) / 1000.0,  # type: ignore[index]
        "ppo_trace": float(ppo["p95_ns"]) / 1000.0,  # type: ignore[index]
        "imitation_numpy": float(imitation["p95_ns"]) / 1000.0,  # type: ignore[index]
    }
    rows = {}
    for interval in intervals_us:
        rows[f"{interval:g}us"] = {
            name: {
                "p95_us": latency,
                "decision_intervals_consumed": latency / interval,
                "missed_full_intervals": max(0, math.ceil(latency / interval) - 1),
                "fits_within_one_interval": latency <= interval,
            }
            for name, latency in p95_us.items()
        }
    return {
        "status": "timing_budget_injection_not_historical_execution_claim",
        "interpretation": (
            "Measured p95 compute latency is converted into decision-grid occupancy. "
            "Historical price-path impact remains blocked by Gate C."
        ),
        "p95_us": p95_us,
        "decision_intervals": rows,
    }


def cuda_decision() -> dict[str, object]:
    available = bool(torch.cuda.is_available())
    result: dict[str, object] = {
        "torch_cuda_available": available,
        "torch_cuda_device_count": int(torch.cuda.device_count()),
        "torch_build": torch.__version__,
    }
    if not available:
        result.update(
            {
                "decision": "no_cuda_device_on_validation_machine",
                "custom_cuda_kernel_implemented": False,
                "cpu_gpu_numeric_comparison_available": False,
                "gate_j_cuda_evidence_status": "hardware_blocked_numeric_gpu_comparison",
            }
        )
        return result
    result["decision"] = "cuda_device_available_benchmark_required"
    return result


def generate_report(
    root: Path,
    config_path: Path,
    extension_path: Path | None,
) -> dict[str, object]:
    config = load_config(config_path)
    raw = root / "results/validation/step30/raw"
    cpp = {
        str(threads): {
            "baseline": read_cpp_timings(raw / f"cpp_baseline_t{threads}.csv"),
            "optimized": read_cpp_timings(raw / f"cpp_optimized_t{threads}.csv"),
        }
        for threads in config.cpp_threads
    }
    for row in cpp.values():
        baseline = float(row["baseline"]["timing"]["median_ns"])  # type: ignore[index]
        optimized = float(row["optimized"]["timing"]["median_ns"])  # type: ignore[index]
        row["speedup"] = baseline / optimized
    models = benchmark_models(root, config)
    report = {
        "schema_version": "performance-engineering-report-v1",
        "step": 30,
        "research_status": config.research_status,
        "hardware": hardware_metadata(),
        "cpp_matching": cpp,
        "model_inference": models,
        "python_cpp_boundary": (
            benchmark_pybind(extension_path, config)
            if extension_path is not None
            else {
                "status": "blocked_missing_pybind11_build_dependency",
                "numeric_comparison_available": False,
            }
        ),
        "latency_injection": latency_injection_panel(models, config.latency_injection_intervals_us),
        "cuda_decision": cuda_decision(),
        "historical_execution_latency_impact": "blocked_gate_c",
        "gate_j_status": (
            "pending_gpu_and_pybind_numeric_comparisons_on_capable_environment"
            if extension_path is None
            else "pending_gpu_numeric_comparison_on_cuda_capable_machine"
        ),
        "scientific_boundary": [
            "fixed-machine engineering timings only",
            "no historical performance claim",
            "no GPU speed claim without a visible CUDA device",
            "no final strategy selection from performance measurements",
        ],
    }
    return report
