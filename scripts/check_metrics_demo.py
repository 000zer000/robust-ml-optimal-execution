#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "data/sample/metrics/step17-metrics-validation/report.json"
EXECUTABLE = native_executable(ROOT, "robust_execution_metrics_demo")

completed = subprocess.run([str(EXECUTABLE)], check=True, capture_output=True, text=True)
if json.loads(completed.stdout) != json.loads(EXPECTED.read_text(encoding="utf-8")):
    raise SystemExit("metrics demo differs from committed report")
print("metrics demo: PASS")
