#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.data_capture.config import load_capture_config  # noqa: E402
from robust_execution.data_capture.offline_fixture import write_offline_fixture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/sample/capture")
    args = parser.parse_args()
    config = load_capture_config(ROOT / "configs/data/binance_capture_pilot.json")
    manifest = asyncio.run(write_offline_fixture(config, args.output_root))
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
