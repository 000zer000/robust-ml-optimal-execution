#!/usr/bin/env python3
"""Generate the immutable deterministic Step 14 sample dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from robust_execution.canonical_data import build_canonical_dataset, load_canonical_data_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("data/sample/canonical"))
    parser.add_argument("--dataset-id", default="step14-canonical-fixture")
    args = parser.parse_args()
    config = load_canonical_data_config(Path("configs/data/binance_canonical_sample.json"))
    manifest = build_canonical_dataset(
        Path("data/sample/validation_step13/step13-full-day-fixture/manifest.json"),
        Path("results/validation/step13/step13-fixture-validation/validation-report.json"),
        config,
        args.output_root,
        dataset_id=args.dataset_id,
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
