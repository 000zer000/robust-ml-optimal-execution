"""Strict, dependency-free TOML configuration loading for bootstrap commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


class ConfigurationError(ValueError):
    """Raised when a configuration violates the declared schema."""


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str
    json: bool


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    seed: int
    scenario: str
    steps: int
    output_directory: Path


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    schema_version: int
    project: str
    logging: LoggingConfig
    bootstrap: BootstrapConfig


def _require_table(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key!r} must be a TOML table")
    return value


def _reject_unknown(data: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigurationError(f"unknown keys in {context}: {', '.join(unknown)}")


def load_config(path: Path) -> ProjectConfig:
    """Load and strictly validate a bootstrap TOML configuration."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"could not load {path}: {exc}") from exc

    _reject_unknown(raw, {"schema_version", "project", "logging", "bootstrap"}, "root")
    logging_raw = _require_table(raw, "logging")
    bootstrap_raw = _require_table(raw, "bootstrap")
    _reject_unknown(logging_raw, {"level", "json"}, "logging")
    _reject_unknown(
        bootstrap_raw,
        {"seed", "scenario", "steps", "output_directory"},
        "bootstrap",
    )

    schema_version = raw.get("schema_version")
    project = raw.get("project")
    level = logging_raw.get("level")
    json_output = logging_raw.get("json")
    seed = bootstrap_raw.get("seed")
    scenario = bootstrap_raw.get("scenario")
    steps = bootstrap_raw.get("steps")
    output_directory = bootstrap_raw.get("output_directory")

    if type(schema_version) is not int or schema_version != 1:
        raise ConfigurationError("schema_version must be integer 1")
    if project != "robust-execution":
        raise ConfigurationError("project must be 'robust-execution'")
    if not isinstance(level, str) or level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigurationError("logging.level must be DEBUG, INFO, WARNING, or ERROR")
    if type(json_output) is not bool:
        raise ConfigurationError("logging.json must be a boolean")
    if type(seed) is not int or seed < 0 or seed >= 2**63:
        raise ConfigurationError("bootstrap.seed must be an integer in [0, 2^63)")
    if not isinstance(scenario, str) or not scenario.strip():
        raise ConfigurationError("bootstrap.scenario must be a non-empty string")
    if type(steps) is not int or not 1 <= steps <= 10_000:
        raise ConfigurationError("bootstrap.steps must be an integer in [1, 10000]")
    if not isinstance(output_directory, str) or not output_directory.strip():
        raise ConfigurationError("bootstrap.output_directory must be a non-empty path")

    return ProjectConfig(
        schema_version=schema_version,
        project=project,
        logging=LoggingConfig(level=level.upper(), json=json_output),
        bootstrap=BootstrapConfig(
            seed=seed,
            scenario=scenario,
            steps=steps,
            output_directory=Path(output_directory),
        ),
    )
