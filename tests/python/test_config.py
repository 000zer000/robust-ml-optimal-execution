from pathlib import Path

import pytest

from robust_execution.config import ConfigurationError, load_config

VALID = """
schema_version = 1
project = "robust-execution"
[logging]
level = "INFO"
json = true
[bootstrap]
seed = 7
scenario = "test"
steps = 3
output_directory = "out"
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_config(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID))
    assert config.bootstrap.seed == 7
    assert config.logging.json is True
    assert config.logging.level == "INFO"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("schema_version = 2", "schema_version"),
        ('project = "other"', "project"),
        ('level = "TRACE"', "logging.level"),
        ("json = 1", "logging.json"),
        ("seed = -1", "bootstrap.seed"),
        ('scenario = ""', "bootstrap.scenario"),
        ("steps = 0", "bootstrap.steps"),
        ('output_directory = ""', "bootstrap.output_directory"),
    ],
)
def test_invalid_scalar_fields_are_rejected(tmp_path: Path, replacement: str, message: str) -> None:
    original_key = replacement.split(" =", maxsplit=1)[0]
    lines = [
        replacement if line.startswith(f"{original_key} =") else line for line in VALID.splitlines()
    ]
    with pytest.raises(ConfigurationError, match=message):
        load_config(_write(tmp_path, "\n".join(lines)))


def test_unknown_root_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_config(_write(tmp_path, VALID.replace("project =", "surprise = 1\nproject =")))


def test_unknown_nested_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="unknown keys in logging"):
        load_config(_write(tmp_path, VALID.replace('level = "INFO"', 'level = "INFO"\nextra = 1')))


def test_missing_table_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match=r"logging.*TOML table"):
        without_logging = VALID.replace('[logging]\nlevel = "INFO"\njson = true\n', "")
        load_config(_write(tmp_path, without_logging))


def test_malformed_toml_is_wrapped(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="could not load"):
        load_config(_write(tmp_path, "[broken"))


def test_missing_file_is_wrapped(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="could not load"):
        load_config(tmp_path / "missing.toml")
