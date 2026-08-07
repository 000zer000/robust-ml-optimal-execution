#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from robust_execution.prediction.temporal_model_artifacts import write_temporal_model_fixture
from robust_execution.prediction.temporal_models import load_temporal_model_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/step23_temporal_deep_engineering.json"
OUTPUT = ROOT / "data/sample/models"


def main() -> None:
    manifest = write_temporal_model_fixture(load_temporal_model_config(CONFIG), OUTPUT)
    print(manifest)


if __name__ == "__main__":
    main()
