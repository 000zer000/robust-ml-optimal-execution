#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "build" / "gcc-debug" / "robust_execution_kernel_demo"
EXPECTED = ROOT / "results" / "sample" / "step7" / "kernel_demo.txt"

if not EXECUTABLE.is_file():
    raise SystemExit(f"missing kernel demo executable: {EXECUTABLE}")
if not EXPECTED.is_file():
    raise SystemExit(f"missing committed kernel demo fixture: {EXPECTED}")

first = subprocess.check_output([str(EXECUTABLE)], text=True)
second = subprocess.check_output([str(EXECUTABLE)], text=True)
expected = EXPECTED.read_text()

if first != second:
    raise SystemExit("kernel demo is not deterministic across two executions")
if first != expected:
    raise SystemExit("kernel demo output differs from committed Step 7 fixture")
print("Step 7 kernel demo: PASS")
