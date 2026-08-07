#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "results" / "sample" / "step8" / "policy_demo.txt"
CANDIDATES = [
    ROOT / "build" / "gcc-debug" / "robust_execution_policy_demo",
    ROOT / "build" / "clang-debug" / "robust_execution_policy_demo",
    ROOT / "build" / "gcc-release" / "robust_execution_policy_demo",
]


def main() -> int:
    executable = next((path for path in CANDIDATES if path.is_file()), None)
    if executable is None:
        raise RuntimeError("policy demo executable not found; build a configured preset first")
    actual = subprocess.check_output([str(executable)])
    expected = EXPECTED.read_bytes()
    if actual != expected:
        raise RuntimeError(
            f"deterministic Step 8 policy demo differs: executable={executable}"
        )
    print(f"policy demo: PASS ({executable.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
