import json
from pathlib import Path
import shutil

from robust_execution.specification import verify_specification_lock


def test_frozen_specification_is_unchanged() -> None:
    assert verify_specification_lock(Path.cwd()) == []


def test_changed_and_missing_files_are_reported(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    lock = {
        "files": {
            "changed.md": "0" * 64,
            "missing.md": "1" * 64,
        }
    }
    (governance / "SPECIFICATION_LOCK.json").write_text(json.dumps(lock), encoding="utf-8")
    (tmp_path / "changed.md").write_text("changed", encoding="utf-8")
    failures = verify_specification_lock(tmp_path)
    assert any(item.startswith("changed:") for item in failures)
    assert any(item.startswith("missing:") for item in failures)


def test_copied_lock_passes(tmp_path: Path) -> None:
    source = Path.cwd()
    (tmp_path / "governance").mkdir()
    shutil.copy(source / "governance" / "SPECIFICATION_LOCK.json", tmp_path / "governance")
    lock = json.loads((source / "governance" / "SPECIFICATION_LOCK.json").read_text())
    for relative in lock["files"]:
        shutil.copy(source / relative, tmp_path / relative)
    assert verify_specification_lock(tmp_path) == []
