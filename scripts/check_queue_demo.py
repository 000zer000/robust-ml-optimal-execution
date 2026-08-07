#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "results/sample/step16/queue_demo.json"
EXECUTABLE = ROOT / "build/gcc-debug/robust_execution_queue_demo"


def main() -> int:
    completed = subprocess.run([str(EXECUTABLE)], check=True, capture_output=True)
    if completed.stdout != EXPECTED.read_bytes():
        raise SystemExit("Step 16 queue demo differs from committed deterministic output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
