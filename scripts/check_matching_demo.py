#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = native_executable(ROOT, "robust_execution_matching_demo")
EXPECTED = ROOT / "data" / "sample" / "matching_engine" / "expected_state.txt"

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
