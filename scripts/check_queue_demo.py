#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "results/sample/step16/queue_demo.json"
CANDIDATES = [
    ROOT / "build" / preset / "robust_execution_queue_demo"
    for preset in ("gcc-debug", "clang-debug", "gcc-release")
]


def main() -> int:
    executable = next((path for path in CANDIDATES if path.is_file()), None)
    if executable is None:
        raise RuntimeError("queue demo executable not found; build a configured preset first")
    if not EXPECTED.is_file():
        raise RuntimeError(f"missing committed queue demo fixture: {EXPECTED}")
    completed = subprocess.run([str(executable)], check=True, capture_output=True)
    if completed.stdout != EXPECTED.read_bytes():
        raise SystemExit("Step 16 queue demo differs from committed deterministic output")
    print(f"Step 16 queue demo: PASS ({executable.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
