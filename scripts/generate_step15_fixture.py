#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.historical_replay import (  # noqa: E402
    build_historical_replay,
    load_historical_replay_config,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/sample/historical_replay")
    parser.add_argument("--replay-id", default="step15-historical-fixture")
    args = parser.parse_args()
    config = load_historical_replay_config(
        ROOT / "configs/data/binance_historical_replay_sample.json"
    )
    manifest = build_historical_replay(
        ROOT / "data/sample/canonical/step14-canonical-fixture/dataset-manifest.json",
        config,
        args.output_root,
        replay_id=args.replay_id,
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
