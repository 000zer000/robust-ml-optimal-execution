#!/usr/bin/env python3
"""Validate headline manuscript claims against canonical committed evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"paper claim validation failed: {message}")


def require_close(actual: float, expected: float, message: str) -> None:
    require(math.isclose(actual, expected, rel_tol=0.0, abs_tol=5e-6), message)


def main() -> int:
    latex = (ROOT / "paper/main.tex").read_text(encoding="utf-8")

    step25 = load_json("data/sample/analysis/prediction-decision-value/report.json")["payload"][
        "engineering_summary"
    ]
    require(
        step25["perfect_label_oracle_can_worsen_execution_fixture"] is True,
        "perfect-label-oracle decision-value finding changed",
    )

    step26 = load_json("data/sample/imitation/imitation-validation/report.json")
    ood = step26["evaluation"]["ood"]
    require_close(
        100.0 * ood["student_raw"]["final_action_agreement"],
        69.29824561403509,
        "raw OOD imitation agreement changed",
    )
    require_close(
        100.0 * ood["student_with_teacher_fallback"]["final_action_agreement"],
        94.78260869565217,
        "fallback OOD imitation agreement changed",
    )
    require_close(
        100.0 * ood["student_with_teacher_fallback"]["fallback_rate"],
        82.6086956521739,
        "OOD teacher-fallback rate changed",
    )

    step28 = load_json("data/sample/robustness/engineering-matrix/report.json")
    ranking28 = step28["ranking_summary"]
    require(len(step28["ranking_rows"]) == 43, "stress-cell count changed")
    require(ranking28["noncentral_case_count"] == 42, "non-central cell count changed")
    require(ranking28["rank_switch_case_count"] == 16, "rank-switch count changed")

    step29 = load_json("data/sample/statistics/engineering-inference/report.json")
    require(len(step29["contrast_rows"]) == 129, "paired contrast count changed")
    require(
        step29["negative_results"]["confidence_intervals_crossing_zero"] == 85,
        "confidence-interval crossing count changed",
    )
    ranking29 = step29["ranking_summary"]
    require(ranking29["case_count"] == 43, "ranking-stability case count changed")
    require(
        ranking29["stable_point_winner_cases_at_0_80"] == 21,
        "stable point-winner count changed",
    )
    require(
        ranking29["unstable_point_winner_cases_at_0_80"] == 22,
        "unstable point-winner count changed",
    )

    step30 = load_json("results/validation/performance_engineering/performance_report.json")
    require_close(
        step30["cpp_matching"]["4"]["optimized"]["throughput_ops_per_second"] / 1_000_000.0,
        17.315932360505014,
        "four-thread matching throughput changed",
    )
    cuda = load_json("evidence/performance/CUDA_GATE.json")
    require_close(
        cuda["models"]["temporal_5s"]["256"]["transfer_inclusive_speedup_vs_cpu"],
        1.7035960601471767,
        "batch-256 temporal CUDA speedup changed",
    )

    manifest = load_json("FINAL_RELEASE_MANIFEST.json")
    require(manifest["python_tests_total"] == 481, "Python test count changed")
    require(manifest["branch_coverage_percent"] == 91, "coverage value changed")
    require(manifest["native_tests_per_matrix"] == 53, "native test count changed")

    required_text = [
        "registered controlled-simulator evidence",
        "perfect-event-oracle",
        "69.30\\%",
        "94.78\\%",
        "82.61\\%",
        "16 of the 42 non-central",
        "129 paired controlled contrasts",
        "85 have 95\\% intervals crossing zero",
        "21 achieve at least 80\\%",
        "22 do not",
        "17.316",
        "1.704",
        "481 tests",
        "91\\%",
        "53/53",
        "required-file and schema contracts",
    ]
    missing = [token for token in required_text if token not in latex]
    require(not missing, f"manuscript is missing registered text: {missing}")

    print("paper claims: PASS (12 artifact-backed findings; repository contract validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
