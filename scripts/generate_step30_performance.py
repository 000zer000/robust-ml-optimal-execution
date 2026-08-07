#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.performance.engineering import canonical_json, generate_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension", type=Path)
    args = parser.parse_args()
    report = generate_report(
        ROOT,
        ROOT / "configs/performance/step30_performance_engineering.json",
        args.extension,
    )
    output = ROOT / "results/validation/step30/performance_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(report) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "path": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
