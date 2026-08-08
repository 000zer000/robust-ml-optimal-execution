#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "LICENSE",
    "CITATION.cff",
    "FINAL_RELEASE_MANIFEST.json",
    "paper/Robust_ML_Optimal_Execution_Research_Paper.pdf",
    "paper/main.tex",
    "paper/references.bib",
    "paper/make_figures.py",
    "docs/release/REPRODUCIBILITY.md",
    "docs/release/RELEASE_NOTES.md",
    "evidence/performance/STEP30_CUDA_GATE.json",
    "evidence/performance/STEP30_PYBIND_BOUNDARY_SUPPLEMENT.json",
    "evidence/data/TARDIS_SAMPLE_COMPATIBILITY.json",
]

BANNED_PUBLIC_PHRASES = [
    "portfolio artifact",
    "public-release candidate",
    "what this project does not claim",
    "zero-budget limitation",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    missing = [
        path
        for path in REQUIRED
        if not (ROOT / path).is_file() or (ROOT / path).stat().st_size == 0
    ]
    if missing:
        print("missing release files:", *missing, sep="\n- ")
        return 1

    paper = ROOT / "paper/Robust_ML_Optimal_Execution_Research_Paper.pdf"
    if paper.stat().st_size < 100_000:
        print("canonical research paper is unexpectedly small")
        return 1

    cuda = json.loads((ROOT / "evidence/performance/STEP30_CUDA_GATE.json").read_text())
    if cuda.get("gate_j_cuda_closed") is not True or cuda.get("status") != "complete":
        print("CUDA gate evidence not closed")
        return 1
    if (
        cuda.get("decision")
        != "gpu_transfer_launch_overhead_inferior_for_registered_batch_one_workloads"
    ):
        print("unexpected CUDA decision")
        return 1

    pybind = json.loads(
        (ROOT / "evidence/performance/STEP30_PYBIND_BOUNDARY_SUPPLEMENT.json").read_text()
    )
    if (
        pybind.get("status") != "pass_numeric_boundary_measurement"
        or pybind.get("extension_semantics") != "diagnostic_sequence_exact_match"
    ):
        print("Python/C++ boundary supplement is incomplete")
        return 1

    tardis = json.loads((ROOT / "evidence/data/TARDIS_SAMPLE_COMPATIBILITY.json").read_text())
    if not tardis.get("normalized_csv_ingestion_compatible"):
        print("Tardis sample compatibility not established")
        return 1

    public_text = "\n".join(
        [
            (ROOT / "README.md").read_text(),
            (ROOT / "paper/main.tex").read_text(),
            (ROOT / "docs/release/RELEASE_NOTES.md").read_text(),
        ]
    ).lower()
    found = [phrase for phrase in BANNED_PUBLIC_PHRASES if phrase in public_text]
    if found:
        print("unprofessional public-facing phrase(s) detected:", *found, sep="\n- ")
        return 1

    citation = (ROOT / "CITATION.cff").read_text()
    if 'version: "0.14.0"' not in citation:
        print("CITATION.cff version is inconsistent with the software release")
        return 1

    manifest = json.loads((ROOT / "FINAL_RELEASE_MANIFEST.json").read_text())
    if manifest.get("python_tests_total") != 480:
        print("final release manifest has a stale Python test count")
        return 1
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        print("final release manifest files must be an object")
        return 1
    invalid_hashes = [
        relative
        for relative, expected in manifest_files.items()
        if not (ROOT / relative).is_file() or sha256(ROOT / relative) != expected
    ]
    if invalid_hashes:
        print("final release manifest has missing or stale files:", *invalid_hashes, sep="\n- ")
        return 1

    print(f"release validation PASS ({len(REQUIRED)} canonical artifacts)")
    print(f"paper sha256: {sha256(paper)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
