#!/usr/bin/env python3
from pathlib import Path

from robust_execution.robustness.matrix import generate_step28_artifacts

ROOT = Path(__file__).resolve().parents[1]
report = generate_step28_artifacts(ROOT)
print(
    "Step 28 robustness matrix generated:",
    report["interactive_case_count"],
    "interactive cases",
)
