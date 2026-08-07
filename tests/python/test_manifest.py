from pathlib import Path

from robust_execution.manifest import git_commit, runtime_manifest, sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "payload"
    path.write_bytes(b"abc")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_git_commit_returns_none_outside_repository(tmp_path: Path) -> None:
    assert git_commit(tmp_path) is None


def test_runtime_manifest_has_required_fields(tmp_path: Path) -> None:
    manifest = runtime_manifest(tmp_path)
    assert manifest["git_commit"] is None
    assert manifest["python"]
    assert manifest["platform"]
    assert manifest["machine"]
