#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "results" / "sample" / "step7" / "kernel_demo.txt"
CANDIDATES = [
    ROOT / "build" / preset / "robust_execution_kernel_demo"
    for preset in ("gcc-debug", "clang-debug", "gcc-release")
]


def main() -> int:
    executable = next((path for path in CANDIDATES if path.is_file()), None)
    if executable is None:
        raise RuntimeError("kernel demo executable not found; build a configured preset first")
    if not EXPECTED.is_file():
        raise RuntimeError(f"missing committed kernel demo fixture: {EXPECTED}")

    first = subprocess.check_output([str(executable)], text=True)
    second = subprocess.check_output([str(executable)], text=True)
    expected = EXPECTED.read_text(encoding="utf-8")
    if first != second:
        raise RuntimeError("kernel demo is not deterministic across two executions")
    if first != expected:
        raise RuntimeError("kernel demo output differs from committed Step 7 fixture")
    print(f"Step 7 kernel demo: PASS ({executable.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
