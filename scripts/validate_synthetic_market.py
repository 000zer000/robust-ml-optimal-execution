#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from native_executable import native_executable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "synthetic"
FIXTURE_DIR = ROOT / "data" / "sample" / "synthetic"
CONFIG_DIR = ROOT / "configs" / "stress_tests"
BINARY = native_executable(ROOT, "robust_execution_synthetic_demo")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config_schema = json.loads(
        (SCHEMA_DIR / "synthetic-market-config-v1.schema.json").read_text(encoding="utf-8")
    )
    manifest_schema = json.loads(
        (SCHEMA_DIR / "synthetic-market-manifest-v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(config_schema)
    Draft202012Validator.check_schema(manifest_schema)

    config_validator = Draft202012Validator(config_schema)
    config_paths = sorted(CONFIG_DIR.glob("synthetic_*.json"))
    if len(config_paths) < 2:
        raise RuntimeError("expected at least two synthetic scenario configs")
    for path in config_paths:
        config_validator.validate(json.loads(path.read_text(encoding="utf-8")))

    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    Draft202012Validator(manifest_schema).validate(manifest)
    if manifest["tape_sha256"] != sha256(FIXTURE_DIR / "tape.txt"):
        raise RuntimeError("synthetic tape hash does not match manifest")
    if manifest["calibration_status"] != "not_calibrated_step9":
        raise RuntimeError("Step 9 fixture must not claim historical calibration")

    summary = (FIXTURE_DIR / "summary.txt").read_text(encoding="utf-8")
    required_summary = {
        "step=9",
        "scenario_class=adversarial_stress",
        "calibration_status=not_calibrated_step9",
        f"tape_sha256={manifest['tape_sha256']}",
    }
    if not required_summary.issubset(set(summary.splitlines())):
        raise RuntimeError("synthetic summary is missing required provenance fields")

    with tempfile.TemporaryDirectory(prefix="re-step9-") as temp:
        output_dir = Path(temp)
        result = subprocess.run(
            [str(BINARY), "--output-dir", str(output_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.encode() != (FIXTURE_DIR / "summary.txt").read_bytes():
            raise RuntimeError("synthetic summary is not byte deterministic")
        for name in ("tape.txt", "manifest.json"):
            if (output_dir / name).read_bytes() != (FIXTURE_DIR / name).read_bytes():
                raise RuntimeError(f"synthetic fixture is not byte deterministic: {name}")

    invalid = json.loads(config_paths[0].read_text(encoding="utf-8"))
    invalid["regimes"][0]["buy_probability_ppm"] = 1_000_001
    if not list(config_validator.iter_errors(invalid)):
        raise RuntimeError("negative synthetic-config schema control unexpectedly passed")

    print(
        "synthetic market: PASS "
        f"({len(config_paths)} configs, 2 schemas, deterministic tape "
        f"{manifest['tape_sha256'][:12]}...)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
