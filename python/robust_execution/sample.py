"""Deterministic bootstrap sample; not a market simulator or empirical result."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robust_execution.config import ProjectConfig
from robust_execution.manifest import canonical_json_bytes, sha256_bytes, sha256_file


def _diagnostic_values(seed: int, steps: int) -> list[int]:
    modulus = 2**63
    return [((seed + index) * 1_000_003 + index * index) % modulus for index in range(steps)]


def create_bootstrap_payload(config: ProjectConfig, config_path: Path) -> dict[str, Any]:
    """Create a deterministic payload from validated configuration only."""
    payload: dict[str, Any] = {
        "artifact_type": "bootstrap_diagnostic",
        "schema_version": 1,
        "project": config.project,
        "scenario": config.bootstrap.scenario,
        "seed": config.bootstrap.seed,
        "steps": config.bootstrap.steps,
        "values": _diagnostic_values(config.bootstrap.seed, config.bootstrap.steps),
        "config_sha256": sha256_file(config_path),
        "research_claim": None,
    }
    payload["payload_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_bootstrap_artifact(
    config: ProjectConfig,
    config_path: Path,
    output_path: Path | None = None,
) -> Path:
    target = output_path or config.bootstrap.output_directory / "bootstrap_result.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(create_bootstrap_payload(config, config_path)))
    return target
