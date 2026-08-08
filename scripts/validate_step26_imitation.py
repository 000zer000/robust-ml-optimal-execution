from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

import jsonschema

from native_executable import native_executable
from robust_execution.imitation.learning import generate_step26_artifacts, validate_step26_report

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/sample/imitation/step26-imitation-validation"
REPORT = OUTPUT / "report.json"
POLICY = OUTPUT / "policy.json"
CONFIG = ROOT / "configs/imitation/step26_imitation_engineering.json"
ORACLE = native_executable(ROOT, "robust_execution_imitation_oracle")
BENCHMARK = ROOT / "results/validation/step26/inference_benchmark.json"
MANIFEST = ROOT / "STEP26_MANIFEST.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_artifact_platform() -> bool:
    return (
        platform.system() == "Linux"
        and platform.machine().lower() in {"amd64", "x86_64"}
        and sys.version_info[:2] == (3, 13)
    )


def main() -> None:
    if not ORACLE.is_file():
        fail("Step 26 C++ teacher oracle is not built")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    validate_step26_report(report)
    jsonschema.validate(
        report,
        json.loads(
            (ROOT / "schemas/imitation/imitation-engineering-report-v1.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    policy_payload = json.loads(POLICY.read_text(encoding="utf-8"))
    jsonschema.validate(
        policy_payload,
        json.loads(
            (ROOT / "schemas/imitation/imitation-policy-artifact-v1.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if sha256(POLICY) != report["artifact"]["sha256"]:
        fail("Step 26 policy artifact hash mismatch")
    dataset_manifest_path = OUTPUT / "teacher-dataset-manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    jsonschema.validate(
        dataset_manifest,
        json.loads(
            (
                ROOT / "schemas/imitation/imitation-teacher-dataset-manifest-v1.schema.json"
            ).read_text(encoding="utf-8")
        ),
    )
    if sha256(dataset_manifest_path) != report["artifact"]["teacher_dataset_manifest_sha256"]:
        fail("Step 26 teacher dataset manifest hash mismatch")
    for table in dataset_manifest["tables"].values():
        path = OUTPUT / table["path"]
        if not path.is_file() or sha256(path) != table["sha256"]:
            fail(f"Step 26 teacher dataset table hash mismatch: {table['path']}")
    if report["teacher"]["policy"] != "step24_shared_ml_mpc_engineering_teacher":
        fail("Step 26 teacher identity changed")
    if len(report["teacher"]["training_class_counts"]) < 3:
        fail("Step 26 engineering teacher action surface is degenerate")
    shift = report["covariate_shift"]
    if shift["dagger_triggered"] is not True or shift["dagger_rounds"] != 1:
        fail("Step 26 corrective-learning fixture no longer triggers")
    if (
        shift["final_validation_raw_action_agreement"]
        <= shift["initial_validation_raw_action_agreement"]
    ):
        fail("Step 26 DAgger correction no longer improves validation rollout agreement")
    holdout = report["evaluation"]["engineering_holdout"]
    if holdout["student_raw"]["raw_action_agreement"] != 1.0:
        fail("Step 26 engineering holdout action agreement changed")
    ood = report["evaluation"]["ood"]
    if (
        ood["student_with_teacher_fallback"]["final_action_agreement"]
        <= ood["student_raw"]["raw_action_agreement"]
    ):
        fail("Step 26 fallback no longer mitigates OOD disagreement")
    if ood["student_with_teacher_fallback"]["final_action_agreement"] >= 1.0:
        fail("Step 26 OOD negative result unexpectedly disappeared")
    if not BENCHMARK.is_file():
        fail("Step 26 inference benchmark is missing")
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    jsonschema.validate(
        benchmark,
        json.loads(
            (ROOT / "schemas/imitation/imitation-inference-benchmark-v1.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if benchmark.get("status") != "engineering_machine_specific_not_step30_performance_claim":
        fail("Step 26 benchmark claim boundary changed")

    with tempfile.TemporaryDirectory() as directory:
        first = Path(directory) / "first"
        second = Path(directory) / "second"
        generate_step26_artifacts(ROOT, ORACLE, CONFIG, first)
        generate_step26_artifacts(ROOT, ORACLE, CONFIG, second)
        artifact_names = (
            "report.json",
            "policy.json",
            "teacher-dataset-manifest.json",
            "teacher_train.csv",
            "teacher_validation.csv",
            "teacher_correction.csv",
            "teacher_engineering_holdout.csv",
            "teacher_ood.csv",
        )
        for name in artifact_names:
            if (first / name).read_bytes() != (second / name).read_bytes():
                fail(f"Step 26 same-host deterministic regeneration mismatch: {name}")
            if canonical_artifact_platform() and (
                (first / name).read_bytes() != (OUTPUT / name).read_bytes()
            ):
                fail(f"Step 26 canonical Linux artifact mismatch: {name}")
        if not canonical_artifact_platform():
            regenerated = json.loads((first / "report.json").read_text(encoding="utf-8"))
            for key in ("teacher", "data", "covariate_shift", "evaluation", "fallback"):
                if regenerated[key] != report[key]:
                    fail(f"Step 26 cross-platform semantic mismatch: {key}")
            regenerated_selection = regenerated["model_selection"]
            if (
                regenerated_selection["selected_alpha"]
                != report["model_selection"]["selected_alpha"]
                or regenerated_selection["selected_hidden_units"]
                != report["model_selection"]["selected_hidden_units"]
            ):
                fail("Step 26 cross-platform model selection mismatch")

    if not MANIFEST.is_file():
        fail("Step 26 release manifest is missing")
    release_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if release_manifest.get("step") != 26:
        fail("Step 26 release manifest identity changed")
    if release_manifest.get("research_status") != report["research_status"]:
        fail("Step 26 release manifest research status mismatch")
    for relative, expected in release_manifest.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            fail(f"Step 26 release manifest hash mismatch: {relative}")

    step25_report = ROOT / "data/sample/analysis/step25-prediction-decision-value/report.json"
    if not step25_report.is_file():
        fail("Step 25 predecessor report is missing")

    print(
        json.dumps(
            {
                "status": "ok",
                "step": 26,
                "teacher_classes": len(report["teacher"]["training_class_counts"]),
                "dagger_rounds": shift["dagger_rounds"],
                "holdout_action_agreement": holdout["student_raw"]["raw_action_agreement"],
                "ood_raw_action_agreement": ood["student_raw"]["raw_action_agreement"],
                "ood_fallback_action_agreement": (
                    ood["student_with_teacher_fallback"]["final_action_agreement"]
                ),
                "research_status": report["research_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
