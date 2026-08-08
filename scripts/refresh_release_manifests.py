#!/usr/bin/env python3
"""Check or refresh the active Step 25-30 and final release-manifest hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_LEDGER = ROOT / "evidence" / "validation-ledger"
ACTIVE_RELEASE_STEPS = range(25, 31)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite stale hashes; the default is a read-only check",
    )
    args = parser.parse_args()

    stale: list[str] = []
    for step in ACTIVE_RELEASE_STEPS:
        path = VALIDATION_LEDGER / f"STEP{step}_MANIFEST.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        files = payload.get("files")
        if not isinstance(files, dict):
            raise SystemExit(f"{path.name}: files must be an object")
        for relative, expected in files.items():
            source = ROOT / relative
            if not source.is_file():
                raise SystemExit(f"{path.name}: missing tracked artifact {relative}")
            actual = sha256(source)
            if actual != expected:
                stale.append(f"{path.name}: {relative}")
                if args.write:
                    files[relative] = actual
        if args.write:
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    final_path = ROOT / "FINAL_RELEASE_MANIFEST.json"
    final_payload = json.loads(final_path.read_text(encoding="utf-8"))
    final_files = final_payload.get("files")
    if not isinstance(final_files, dict):
        raise SystemExit(f"{final_path.name}: files must be an object")
    for relative, expected in final_files.items():
        source = ROOT / relative
        if not source.is_file():
            raise SystemExit(f"{final_path.name}: missing tracked artifact {relative}")
        actual = sha256(source)
        if actual != expected:
            stale.append(f"{final_path.name}: {relative}")
            if args.write:
                final_files[relative] = actual
    if args.write:
        final_path.write_text(
            json.dumps(final_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if stale and not args.write:
        print("stale release-manifest hashes:")
        print("\n".join(f"- {entry}" for entry in stale))
        return 1
    action = "refreshed" if args.write else "verified"
    print(f"release manifests: {action} ({len(stale)} stale hashes found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
