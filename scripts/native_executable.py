"""Resolve a built native executable without assuming a compiler preset."""

from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_PRESETS = ("gcc-debug", "clang-debug", "gcc-release")


def native_executable(root: Path, name: str, *, environment: str | None = None) -> Path:
    """Return an explicit override or the first available supported-preset executable."""
    if environment and (override := os.environ.get(environment)):
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"{environment} does not name a built executable: {path}")
        return path
    candidates = [root / "build" / preset / name for preset in SUPPORTED_PRESETS]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        locations = ", ".join(str(path.relative_to(root)) for path in candidates)
        raise RuntimeError(f"{name} is not built; checked {locations}")
    return executable
