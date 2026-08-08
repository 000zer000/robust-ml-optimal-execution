#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from robust_execution.statistics.inference import generate_step29_artifacts  # noqa: E402

if __name__ == "__main__":
    report = generate_step29_artifacts(ROOT)
    print(f"Step 29 generated: {report['engineering_contrast_count']} engineering contrasts")
