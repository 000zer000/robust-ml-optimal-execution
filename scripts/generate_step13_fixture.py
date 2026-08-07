#!/usr/bin/env python3
from pathlib import Path

from robust_execution.data_validation.fixture import generate_step13_capture_fixture

if __name__ == "__main__":
    print(generate_step13_capture_fixture(Path("data/sample/validation_step13")))
