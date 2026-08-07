from __future__ import annotations

from pathlib import Path

from robust_execution.cli import main


ROOT = Path(__file__).resolve().parents[2]


def test_verify_historical_replay_cli(capsys) -> None:
    code = main(
        [
            "verify-historical-replay",
            str(
                ROOT
                / "data/sample/historical_replay/step15-historical-fixture/replay-manifest.json"
            ),
        ]
    )
    assert code == 0
    assert '"status": "ok"' in capsys.readouterr().out


def test_build_historical_replay_cli(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "build-historical-replay",
            str(ROOT / "data/sample/canonical/step14-canonical-fixture/dataset-manifest.json"),
            str(ROOT / "configs/data/binance_historical_replay_sample.json"),
            "--output-root",
            str(tmp_path),
            "--replay-id",
            "cli-replay",
        ]
    )
    assert code == 0
    assert (tmp_path / "cli-replay/replay-manifest.json").is_file()
    assert '"status": "ok"' in capsys.readouterr().out
