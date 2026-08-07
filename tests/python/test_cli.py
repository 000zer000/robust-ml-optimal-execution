import json
from pathlib import Path

from robust_execution.cli import main


def test_validate_config_command(capsys: object) -> None:
    del capsys
    assert main(["validate-config", "configs/bootstrap/sample.toml"]) == 0


def test_verify_spec_command() -> None:
    assert main(["verify-spec", "--root", str(Path.cwd())]) == 0


def test_bootstrap_sample_command(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    assert (
        main(
            [
                "bootstrap-sample",
                "configs/bootstrap/sample.toml",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["research_claim"] is None


def test_invalid_config_returns_two(tmp_path: Path, capsys: object) -> None:
    del capsys
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("schema_version = 9", encoding="utf-8")
    assert main(["validate-config", str(invalid)]) == 2


def test_event_model_sample_and_verify_audit_commands(tmp_path: Path) -> None:
    output = tmp_path / "event-model"
    assert main(["event-model-sample", "--output-dir", str(output)]) == 0
    assert main(["verify-audit", str(output / "audit.jsonl")]) == 0


def test_verify_audit_command_reports_model_error(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("not-json\n", encoding="utf-8")
    assert main(["verify-audit", str(invalid)]) == 3


def test_step13_validation_and_verify_commands(tmp_path: Path) -> None:
    output = tmp_path / "validation"
    assert (
        main(
            [
                "validate-raw-data",
                "data/sample/validation_step13/step13-full-day-fixture/manifest.json",
                "configs/data/binance_raw_validation.json",
                "--output-root",
                str(output),
                "--validation-id",
                "cli-step13",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "verify-data-validation",
                str(output / "cli-step13" / "validation-report.json"),
            ]
        )
        == 0
    )


def test_step13_invalid_config_returns_five(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    assert (
        main(
            [
                "validate-raw-data",
                "data/sample/validation_step13/step13-full-day-fixture/manifest.json",
                str(invalid),
                "--output-root",
                str(tmp_path / "out"),
            ]
        )
        == 5
    )
