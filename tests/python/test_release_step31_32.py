import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_research_paper_and_sources_exist():
    pdf = ROOT / "paper/Robust_ML_Optimal_Execution_Research_Paper.pdf"
    assert pdf.is_file() and pdf.stat().st_size > 100_000
    for rel in [
        "paper/main.tex",
        "paper/references.bib",
        "paper/make_figures.py",
        "paper/CLAIM_TRACEABILITY.md",
        "docs/research/PROFESSOR_REVIEW_GUIDE.md",
        "scripts/validate_paper_claims.py",
    ]:
        assert (ROOT / rel).is_file()
    latex = (ROOT / "paper/main.tex").read_text()
    assert "478 tests" not in latex
    assert "561/561" not in latex
    assert "registered controlled-simulator evidence" in latex
    figure_script = (ROOT / "paper/make_figures.py").read_text()
    assert "/mnt/data" not in figure_script
    for rel in [
        "data/sample/analysis/step25-prediction-decision-value/report.json",
        "data/sample/imitation/step26-imitation-validation/report.json",
        "data/sample/rl/step27-ppo-engineering/report.json",
        "data/sample/robustness/step28-engineering-matrix/report.json",
        "data/sample/statistics/step29-engineering-inference/report.json",
        "results/validation/step30/performance_report.json",
        "evidence/performance/STEP30_CUDA_GATE.json",
    ]:
        assert rel in figure_script


def test_cuda_gate_is_closed_and_batch_one_cpu_selected():
    data = json.loads((ROOT / "evidence/performance/STEP30_CUDA_GATE.json").read_text())
    assert data["gate_j_cuda_closed"] is True
    assert (
        data["decision"]
        == "gpu_transfer_launch_overhead_inferior_for_registered_batch_one_workloads"
    )
    for model in data["models"].values():
        assert model["1"]["transfer_inclusive_gpu_faster"] is False


def test_temporal_large_batch_gpu_gain_is_preserved():
    data = json.loads((ROOT / "evidence/performance/STEP30_CUDA_GATE.json").read_text())
    cell = data["models"]["temporal_5s"]["256"]
    assert cell["transfer_inclusive_gpu_faster"] is True
    assert cell["transfer_inclusive_speedup_vs_cpu"] > 1.6


def test_public_surface_uses_academic_framing():
    text = "\n".join(
        [
            (ROOT / "README.md").read_text(),
            (ROOT / "paper/main.tex").read_text(),
            (ROOT / "docs/release/RELEASE_NOTES.md").read_text(),
        ]
    ).lower()
    for phrase in [
        "portfolio artifact",
        "public-release candidate",
        "what this project does not claim",
        "zero-budget limitation",
    ]:
        assert phrase not in text


def test_application_preparation_material_is_not_public():
    assert not (ROOT / "docs/applications").exists()
    assert not (ROOT / "docs/report/Robust_Execution_Technical_Report.pdf").exists()


def test_release_version_and_citation_are_consistent():
    citation = (ROOT / "CITATION.cff").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'version: "0.14.0"' in citation
    assert 'version = "0.14.0"' in pyproject
