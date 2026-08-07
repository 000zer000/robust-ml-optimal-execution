#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "results/sample/step15/historical_demo.txt"
EXECUTABLE = ROOT / "build/gcc-debug/robust_execution_historical_demo"


def main() -> int:
    completed = subprocess.run([str(EXECUTABLE)], check=True, capture_output=True)
    if completed.stdout != EXPECTED.read_bytes():
        raise SystemExit("Step 15 historical demo differs from committed deterministic output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
