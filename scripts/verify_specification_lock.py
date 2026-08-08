#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.specification import verify_specification_lock  # noqa: E402

failures = verify_specification_lock(ROOT)
if failures:
    print(json.dumps({"status": "failed", "failures": failures}, indent=2))
    raise SystemExit(1)
print(json.dumps({"status": "ok", "checked_files": 7}))
