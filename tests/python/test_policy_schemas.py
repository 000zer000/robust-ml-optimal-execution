from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_policy_contract_validation_script() -> None:
    path = ROOT / "scripts" / "validate_policy_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_policy_contracts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
