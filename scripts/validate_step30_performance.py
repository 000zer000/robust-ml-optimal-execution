#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "results/validation/step30/performance_report.json"
CONFIG = ROOT / "configs/performance/step30_performance_engineering.json"
HASHES = ROOT / "results/validation/step30/artifact_hashes.json"
RELEASE_MANIFEST = ROOT / "STEP30_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas/performance" / name).read_text(encoding="utf-8"))


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    jsonschema.validate(config, load_schema("performance-engineering-config-v1.schema.json"))
    jsonschema.validate(report, load_schema("performance-engineering-report-v1.schema.json"))
    if report["historical_execution_latency_impact"] != "blocked_gate_c":
        fail("Step 30 invented historical latency impact")
    cuda = report["cuda_decision"]
    if cuda["torch_cuda_available"] is False:
        if cuda["cpu_gpu_numeric_comparison_available"] is not False:
            fail("Step 30 fabricated a CPU/GPU comparison")
        if report["gate_j_status"].startswith("pass"):
            fail("Step 30 passed Gate J without GPU evidence")
    boundary = report["python_cpp_boundary"]
    if boundary.get("status") == "blocked_missing_pybind11_build_dependency":
        if boundary.get("numeric_comparison_available") is not False:
            fail("Step 30 fabricated a Python/C++ boundary number")
    for threads, row in report["cpp_matching"].items():
        baseline = row["baseline"]
        optimized = row["optimized"]
        if baseline["checksum"] != optimized["checksum"]:
            fail(f"Step 30 matching checksum changed at {threads} threads")
        if baseline["timing"]["samples"] < 5 or optimized["timing"]["samples"] < 5:
            fail("Step 30 C++ timing repetition requirement failed")
        if row["speedup"] <= 0:
            fail("Step 30 invalid C++ speedup")
    compiled = json.loads(
        (ROOT / "results/validation/step30/raw/compiled_inference.json").read_text(
            encoding="utf-8"
        )
    )
    if compiled["temporal_5s"]["torch_export_status"] != "captured":
        fail("Step 30 temporal export capture failed")
    if not compiled["temporal_5s"]["fullgraph_status"].startswith("unsupported:"):
        fail("Step 30 temporal fullgraph oracle changed")
    if not HASHES.is_file():
        fail("Step 30 artifact hash manifest missing")
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    for relative, expected in hashes["files"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 30 artifact hash mismatch: {relative}")
    if RELEASE_MANIFEST.is_file():
        release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
        for relative, expected in release.get("files", {}).items():
            path = ROOT / relative
            if not path.is_file() or sha256(path) != expected:
                fail(f"Step 30 release manifest hash mismatch: {relative}")
    print(json.dumps({
        "status": "ok",
        "step": 30,
        "gate_j": report["gate_j_status"],
        "cuda_available": cuda["torch_cuda_available"],
        "cpp_threads": sorted(report["cpp_matching"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
