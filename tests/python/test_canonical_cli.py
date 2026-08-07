from __future__ import annotations

from pathlib import Path

from robust_execution.cli import main


def test_canonical_cli_round_trip(tmp_path: Path, capsys) -> None:
    code = main([
        "build-canonical-data",
        "data/sample/validation_step13/step13-full-day-fixture/manifest.json",
        "results/validation/step13/step13-fixture-validation/validation-report.json",
        "configs/data/binance_canonical_sample.json",
        "--output-root",
        str(tmp_path),
        "--dataset-id",
        "cli-canonical",
    ])
    assert code == 0
    manifest = tmp_path / "cli-canonical/dataset-manifest.json"
    assert manifest.exists()
    capsys.readouterr()
    assert main(["verify-canonical-data", str(manifest)]) == 0
    assert '"status": "ok"' in capsys.readouterr().out
