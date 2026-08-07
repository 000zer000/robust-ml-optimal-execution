#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from robust_execution.analysis.prediction_decision_value import (
    build_report,
    canonical_json,
    load_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/analysis/step25_prediction_decision_value_engineering.json"
OUT = ROOT / "data/sample/analysis/step25-prediction-decision-value/report.json"


def main() -> None:
    config = load_config(CONFIG)
    executable = Path(
        os.environ.get(
            "RE_STEP25_CONTROLLER_EXE",
            ROOT / "build/gcc-debug/robust_execution_ml_mpc_demo",
        )
    )
    report = build_report(ROOT, config, executable)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(canonical_json(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
