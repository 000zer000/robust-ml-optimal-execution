from pathlib import Path

from robust_execution.config import load_config
from robust_execution.manifest import canonical_json_bytes, sha256_bytes
from robust_execution.sample import create_bootstrap_payload, write_bootstrap_artifact


def test_bootstrap_artifact_is_byte_deterministic(tmp_path: Path) -> None:
    config_path = Path("configs/bootstrap/sample.toml")
    config = load_config(config_path)
    first = write_bootstrap_artifact(config, config_path, tmp_path / "first.json")
    second = write_bootstrap_artifact(config, config_path, tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()


def test_payload_digest_covers_payload_without_digest() -> None:
    config_path = Path("configs/bootstrap/sample.toml")
    payload = create_bootstrap_payload(load_config(config_path), config_path)
    digest = payload.pop("payload_sha256")
    assert digest == sha256_bytes(canonical_json_bytes(payload))
    assert payload["research_claim"] is None
