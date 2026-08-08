"""Specification-lock verification used by local commands and CI."""

from __future__ import annotations

import json
from pathlib import Path

from robust_execution.manifest import sha256_file


class SpecificationLockError(RuntimeError):
    """Raised when a frozen document differs from its approved hash."""


def verify_specification_lock(root: Path) -> list[str]:
    lock_path = root / "governance" / "SPECIFICATION_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for relative_path, expected_hash in lock["files"].items():
        path = root / relative_path
        if not path.is_file():
            failures.append(f"missing: {relative_path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            failures.append(
                f"changed: {relative_path} expected={expected_hash} actual={actual_hash}"
            )
    return failures
