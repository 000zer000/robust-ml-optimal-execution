#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "build" / "gcc-debug" / "robust_execution_matching_demo"
EXPECTED = ROOT / "data" / "sample" / "matching_engine" / "expected_state.txt"

if not EXECUTABLE.is_file():
    print(f"missing demo executable: {EXECUTABLE}")
    raise SystemExit(1)
if not EXPECTED.is_file():
    print(f"missing expected matching-engine state: {EXPECTED}")
    raise SystemExit(1)

completed = subprocess.run(
    [str(EXECUTABLE)],
    check=False,
    capture_output=True,
    text=True,
)
if completed.returncode != 0:
    sys.stderr.write(completed.stderr)
    raise SystemExit(completed.returncode)
if completed.stdout != EXPECTED.read_text(encoding="utf-8"):
    print("matching-engine deterministic hand tape differs from expected output")
    raise SystemExit(1)
print("matching-engine deterministic hand tape: PASS")
