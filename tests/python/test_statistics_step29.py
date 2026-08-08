from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from robust_execution.statistics.inference import (
    PairedHistoricalRow,
    StatisticalError,
    Step29Config,
    autocorrelation,
    bootstrap_tier1_guardrails,
    canonical_json,
    cvar95,
    equal_instrument_paired_estimate,
    generate_step29_artifacts,
    holm_adjust,
    load_config,
    moving_block_indices,
    paired_block_inference,
    select_block_length,
    validate_config,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/statistics/step29_statistics_engineering.json"
OUTPUT = ROOT / "data/sample/statistics/step29-engineering-inference"
STEP28 = ROOT / "data/sample/robustness/step28-engineering-matrix/report.json"


def test_config_and_gate_boundary() -> None:
    config = load_config(CONFIG)
    assert config.step == 29
    assert config.historical_confirmatory_analysis_blocked
    with pytest.raises(StatisticalError):
        validate_config(
            Step29Config(**{**config.__dict__, "historical_confirmatory_analysis_blocked": False})
        )


def test_block_length_follows_frozen_acf_rule() -> None:
    report = json.loads(STEP28.read_text())
    metrics = report["interactive_metrics"]["central_reference"]
    seeds = (27, 127, 227, 327, 427)
    ppo = np.mean([metrics[f"ppo_seed_{seed}"]["episode_costs_bps"] for seed in seeds], axis=0)
    diff = ppo - np.asarray(metrics["liquidity_aware"]["episode_costs_bps"])
    block, acf = select_block_length(diff, threshold=0.1, minimum=2, maximum=7)
    assert block == 5
    assert abs(acf["5"]) < 0.1 and abs(acf["6"]) < 0.1


def test_autocorrelation_rejects_bad_lag() -> None:
    with pytest.raises(StatisticalError):
        autocorrelation([1, 2, 3], 0)
    with pytest.raises(StatisticalError):
        autocorrelation([1, 2, 3], 3)


def test_artifact_json_uses_canonical_cross_kernel_precision() -> None:
    left = canonical_json({"value": 1.23456789012341})
    right = canonical_json({"value": 1.23456789012349})
    assert left == right == '{"value":1.23456789012}'
    with pytest.raises(StatisticalError, match="finite"):
        canonical_json({"value": float("nan")})


def test_moving_block_bootstrap_is_deterministic_and_contiguous() -> None:
    left = moving_block_indices(12, 3, 8, 99)
    right = moving_block_indices(12, 3, 8, 99)
    assert np.array_equal(left, right)
    assert left.shape == (8, 12)
    for sample in left:
        for offset in (0, 3, 6, 9):
            block = sample[offset : offset + 3]
            assert np.all((block[1:] - block[:-1]) % 12 == 1)


def test_moving_block_rejects_invalid_dimensions() -> None:
    with pytest.raises(StatisticalError):
        moving_block_indices(0, 1, 10, 1)
    with pytest.raises(StatisticalError):
        moving_block_indices(4, 5, 10, 1)


def test_paired_inference_detects_clear_effect_and_preserves_pairing() -> None:
    comparator = np.arange(1.0, 25.0)
    policy = comparator - 2.0
    result = paired_block_inference(
        policy, comparator, block_length=3, repetitions=2048, seed=12, alpha=0.05
    )
    assert result["mean_difference_bps"] == pytest.approx(-2.0)
    assert result["mean_ci95_bps"][1] < 0.0
    assert result["raw_two_sided_p_value"] < 0.01


def test_paired_inference_rejects_misaligned_and_nonfinite() -> None:
    with pytest.raises(StatisticalError):
        paired_block_inference([1, 2], [1], block_length=1, repetitions=10, seed=1, alpha=0.05)
    with pytest.raises(StatisticalError):
        paired_block_inference(
            [1, float("nan")], [1, 2], block_length=1, repetitions=10, seed=1, alpha=0.05
        )


def test_holm_adjustment_is_monotone_and_bounded() -> None:
    adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.20})
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] >= adjusted["a"]
    assert adjusted["c"] <= 1.0
    with pytest.raises(StatisticalError):
        holm_adjust({"bad": 1.2})


def test_equal_instrument_weighting_prevents_episode_count_domination() -> None:
    rows = [
        PairedHistoricalRow("BTC", "buy", "small", "d1", 1, 3),
        PairedHistoricalRow("BTC", "sell", "small", "d1", 1, 3),
        PairedHistoricalRow("BTC", "buy", "small", "d2", 1, 3),
        PairedHistoricalRow("ETH", "buy", "small", "d1", 5, 3),
    ]
    result = equal_instrument_paired_estimate(rows)
    assert result["per_instrument_mean_difference_bps"] == {"BTC": -2.0, "ETH": 2.0}
    assert result["equal_instrument_weighted_mean_difference_bps"] == pytest.approx(0.0)
    with pytest.raises(StatisticalError):
        equal_instrument_paired_estimate([])


def test_cvar95_and_guardrails_follow_frozen_formulas() -> None:
    comparator = np.linspace(0.0, 10.0, 40)
    policy = comparator + 0.1
    completion = np.ones(40)
    result = bootstrap_tier1_guardrails(
        policy,
        comparator,
        completion,
        completion,
        block_length=3,
        repetitions=1024,
        seed=7,
    )
    assert cvar95(policy) > cvar95(comparator)
    assert result["completion_pass"]
    assert result["cvar95_allowed_margin_bps"] >= 1.0
    assert result["cvar95_pass"]


def test_guardrails_reject_bad_shape() -> None:
    with pytest.raises(StatisticalError):
        bootstrap_tier1_guardrails(
            [1, 2], [1], [1, 1], [1, 1], block_length=1, repetitions=10, seed=1
        )


def test_generated_report_preserves_negative_results_and_tier1_lock() -> None:
    report = json.loads((OUTPUT / "report.json").read_text())
    assert report["tier1_confirmatory"]["status"] == "blocked_gate_c"
    assert not report["locked_historical_test_opened"]
    assert report["method"]["selected_engineering_block_length"] == 5
    assert report["engineering_contrast_count"] == 129
    assert report["negative_results"]["confidence_intervals_crossing_zero"] > 0
    assert report["ranking_summary"]["unstable_point_winner_cases_at_0_80"] > 0


def test_central_engineering_contrast_is_not_promoted_to_winner() -> None:
    report = json.loads((OUTPUT / "report.json").read_text())
    rows = {
        row["policy"]: row
        for row in report["contrast_rows"]
        if row["case_id"] == "central_reference"
    }
    ppo = rows["ppo_aggregate"]
    assert ppo["mean_difference_bps"] > 0.0
    assert ppo["mean_ci95_bps"][0] < 0.0 < ppo["mean_ci95_bps"][1]


def test_manifest_hashes_match_committed_artifacts() -> None:
    import hashlib

    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest() == expected


def test_full_artifact_regeneration_is_byte_deterministic(tmp_path: Path) -> None:
    rerun = tmp_path / "repo"
    for source in (CONFIG, STEP28):
        target = rerun / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    generate_step29_artifacts(rerun)
    regenerated = rerun / "data/sample/statistics/step29-engineering-inference"
    for name in ("report.json", "contrasts.csv", "ranking-stability.json", "manifest.json"):
        assert (regenerated / name).read_bytes() == (OUTPUT / name).read_bytes()
