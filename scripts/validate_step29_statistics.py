#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.statistics.inference import generate_step29_artifacts  # noqa: E402

OUTPUT = ROOT / "data/sample/statistics/step29-engineering-inference"
REPORT = OUTPUT / "report.json"
MANIFEST = OUTPUT / "manifest.json"
CONFIG = ROOT / "configs/statistics/step29_statistics_engineering.json"
STEP28 = ROOT / "data/sample/robustness/step28-engineering-matrix/report.json"
RELEASE_MANIFEST = ROOT / "evidence/validation-ledger/STEP29_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema(name: str) -> dict[str, object]:
    return json.loads((ROOT / "schemas/statistics" / name).read_text(encoding="utf-8"))


def copy_dependency(source: Path, target_root: Path) -> None:
    target = target_root / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema("statistics-engineering-report-v1.schema.json"))
    jsonschema.validate(config, schema("statistics-engineering-config-v1.schema.json"))
    jsonschema.validate(manifest, schema("statistics-engineering-manifest-v1.schema.json"))
    if manifest["config_sha256"] != sha256(CONFIG):
        fail("Step 29 config hash mismatch")
    if manifest["step28_report_sha256"] != sha256(STEP28):
        fail("Step 29 Step 28 dependency hash mismatch")
    for name, expected in manifest["files"].items():
        if sha256(OUTPUT / name) != expected:
            fail(f"Step 29 artifact hash mismatch: {name}")
    if report["locked_historical_test_opened"] is not False:
        fail("Step 29 opened the locked historical test")
    if report["tier1_confirmatory"]["status"] != "blocked_gate_c":
        fail("Step 29 promoted a synthetic Tier-1 result")
    if report["method"]["selected_engineering_block_length"] != 5:
        fail("Step 29 engineering block-length oracle changed")
    if report["method"]["iid_episode_bootstrap_used_for_primary_inference"] is not False:
        fail("Step 29 enabled IID primary inference")
    if report["engineering_contrast_count"] != 129:
        fail("Step 29 engineering contrast count changed")
    if report["negative_results"]["confidence_intervals_crossing_zero"] <= 0:
        fail("Step 29 negative/inconclusive results disappeared")
    if report["ranking_summary"]["unstable_point_winner_cases_at_0_80"] <= 0:
        fail("Step 29 ranking uncertainty disappeared")
    with tempfile.TemporaryDirectory() as directory:
        rerun_root = Path(directory) / "repo"
        for source in (CONFIG, STEP28):
            copy_dependency(source, rerun_root)
        generate_step29_artifacts(rerun_root)
        rerun = rerun_root / "data/sample/statistics/step29-engineering-inference"
        for name in ("report.json", "contrasts.csv", "ranking-stability.json", "manifest.json"):
            if (rerun / name).read_bytes() != (OUTPUT / name).read_bytes():
                fail(f"Step 29 deterministic regeneration mismatch: {name}")
    if RELEASE_MANIFEST.is_file():
        release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
        for relative, expected in release.get("files", {}).items():
            path = ROOT / relative
            if not path.is_file() or sha256(path) != expected:
                fail(f"Step 29 release manifest hash mismatch: {relative}")
    print(
        json.dumps(
            {
                "status": "ok",
                "step": 29,
                "block_length": report["method"]["selected_engineering_block_length"],
                "contrasts": report["engineering_contrast_count"],
                "tier1": report["tier1_confirmatory"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
