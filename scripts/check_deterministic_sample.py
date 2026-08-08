#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.config import load_config  # noqa: E402
from robust_execution.sample import write_bootstrap_artifact  # noqa: E402

config_path = ROOT / "configs" / "bootstrap" / "sample.toml"
config = load_config(config_path)
with tempfile.TemporaryDirectory() as directory:
    first = write_bootstrap_artifact(config, config_path, Path(directory) / "first.json")
    second = write_bootstrap_artifact(config, config_path, Path(directory) / "second.json")
    if first.read_bytes() != second.read_bytes():
        raise SystemExit("deterministic sample mismatch")
print("deterministic sample: PASS")
