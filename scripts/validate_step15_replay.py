#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from robust_execution.historical_replay import verify_historical_replay  # noqa: E402


def main() -> int:
    manifest = ROOT / "data/sample/historical_replay/step15-historical-fixture/replay-manifest.json"
    config_schema = json.loads(
        (ROOT / "schemas/data/historical-replay-config-v1.schema.json").read_text()
    )
    manifest_schema = json.loads(
        (ROOT / "schemas/data/historical-replay-manifest-v1.schema.json").read_text()
    )
    config_instance = json.loads(
        (ROOT / "configs/data/binance_historical_replay_sample.json").read_text()
    )
    manifest_instance = json.loads(manifest.read_text())
    jsonschema.Draft202012Validator.check_schema(config_schema)
    jsonschema.Draft202012Validator.check_schema(manifest_schema)
    jsonschema.Draft202012Validator(config_schema).validate(config_instance)
    jsonschema.Draft202012Validator(manifest_schema).validate(manifest_instance)
    result = verify_historical_replay(manifest)
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/generate_step15_fixture.py"),
                "--output-root",
                str(output),
            ],
            check=True,
            cwd=ROOT,
        )
        regenerated = output / "step15-historical-fixture/replay-manifest.json"
        regenerated_result = verify_historical_replay(regenerated)
        if manifest.read_bytes() != regenerated.read_bytes():
            raise SystemExit("Step 15 replay manifest is not deterministic")
        committed_root = manifest.parent
        regenerated_root = regenerated.parent
        for relative in (
            "replay-manifest.sha256.json",
            "tables/replay_events/columns.json.gz",
            "tables/replay_observations/columns.json.gz",
            "tables/connection_integrity/columns.json.gz",
        ):
            if (committed_root / relative).read_bytes() != (regenerated_root / relative).read_bytes():
                raise SystemExit(f"Step 15 artifact is not deterministic: {relative}")
        if result != regenerated_result:
            raise SystemExit("Step 15 verification result changed on regeneration")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
