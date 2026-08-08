#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.rl import generate_step27_artifacts  # noqa: E402


def main() -> None:
    generate_step27_artifacts(ROOT)
    print("Step 27 PPO engineering artifacts generated")


if __name__ == "__main__":
    main()
