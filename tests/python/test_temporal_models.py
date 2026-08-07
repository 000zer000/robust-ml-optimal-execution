from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch")

from robust_execution.prediction.simple_models import HORIZON_TARGETS, TrainingRow
from robust_execution.prediction.temporal_model_artifacts import (
    verify_temporal_model_fixture,
    write_temporal_model_fixture,
)
from robust_execution.prediction.temporal_models import (
    CausalConvLSTM,
    TemporalModelError,
    base_rate_proxy,
    build_sequences,
    decision_proxy,
    fit_feature_scaler,
    fit_selected_temporal_model,
    generate_temporal_training_rows,
    load_model_from_payloads,
    load_temporal_model_config,
    ood_diagnostics,
    prediction_rows,
    reverse_sequences,
    select_temporal_hyperparameters,
    sequence_matrix,
    split_sequences,
    state_dict_payload,
    temporal_model_card,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/models/step23_temporal_deep_engineering.json"


def _config():
    return load_temporal_model_config(CONFIG)


def _fixture():
    config = _config()
    rows = generate_temporal_training_rows(config)
    sequences = build_sequences(rows, config)
    return config, rows, sequences, split_sequences(sequences, config)


def test_config_preserves_frozen_contract() -> None:
    config = _config()
    assert config.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.candidate_horizons == ("250ms", "1s", "5s")
    assert len(config.feature_names) == 20
    assert config.sequence_length == 8
    assert config.architecture == "causal_conv1d_lstm"
    assert not config.final_model_selection_allowed
    assert not config.use_engineering_holdout_for_selection
    assert not config.use_decision_proxy_for_selection


def test_sequence_counts_and_chronological_splits() -> None:
    config, rows, sequences, split = _fixture()
    assert len(rows) == 4800
    assert len(sequences) == 2000
    assert {name: len(values) for name, values in split.items()} == {
        "train": 1000,
        "validation": 400,
        "calibration": 200,
        "engineering_holdout": 400,
    }
    for sequence in sequences:
        assert len({row.day_index for row in sequence.rows}) == 1
        assert len({row.symbol for row in sequence.rows}) == 1
        assert len({row.passive_side for row in sequence.rows}) == 1
        assert sequence.endpoint.decision_index == sequence.end_decision_index


def test_future_row_mutation_cannot_change_earlier_sequence() -> None:
    config, rows, sequences, _ = _fixture()
    target = next(
        item for item in sequences if item.day_index == 1 and item.end_decision_index == 7
    )
    future_index = next(
        index
        for index, row in enumerate(rows)
        if row.day_index == target.day_index
        and row.symbol == target.symbol
        and row.passive_side == target.passive_side
        and row.decision_index == 8
    )
    changed_feature = dict(rows[future_index].feature)
    changed_feature["spread_ticks"] += 1000
    mutated = list(rows)
    mutated[future_index] = replace(rows[future_index], feature=changed_feature)
    rebuilt = build_sequences(mutated, config)
    same = next(item for item in rebuilt if item.sequence_id == target.sequence_id)
    x_original, _ = sequence_matrix([target], config, "1s")
    x_changed, _ = sequence_matrix([same], config, "1s")
    assert np.array_equal(x_original, x_changed)


def test_causal_past_mutation_changes_sequence() -> None:
    config, rows, sequences, _ = _fixture()
    target = next(
        item for item in sequences if item.day_index == 1 and item.end_decision_index == 7
    )
    past_index = next(
        index
        for index, row in enumerate(rows)
        if row.day_index == target.day_index
        and row.symbol == target.symbol
        and row.passive_side == target.passive_side
        and row.decision_index == 3
    )
    changed_feature = dict(rows[past_index].feature)
    changed_feature["spread_ticks"] += 1000
    mutated = list(rows)
    mutated[past_index] = replace(rows[past_index], feature=changed_feature)
    same = next(
        item
        for item in build_sequences(mutated, config)
        if item.sequence_id == target.sequence_id
    )
    x_original, _ = sequence_matrix([target], config, "1s")
    x_changed, _ = sequence_matrix([same], config, "1s")
    assert not np.array_equal(x_original, x_changed)


def test_scaler_is_fit_on_training_timesteps_only() -> None:
    config, _, _, split = _fixture()
    x_train, _ = sequence_matrix(split["train"], config, "1s")
    scaler = fit_feature_scaler(x_train)
    expected = x_train.astype(np.float64).reshape(-1, x_train.shape[-1]).mean(axis=0)
    assert np.allclose(np.asarray(scaler.mean), expected, rtol=1e-6, atol=1e-5)


def test_temporal_architecture_is_order_sensitive() -> None:
    import torch

    torch.manual_seed(7)
    network = CausalConvLSTM(20, 8, 8, 3)
    x = torch.arange(1 * 8 * 20, dtype=torch.float32).reshape(1, 8, 20) / 100.0
    original = network(x).detach().numpy()
    reversed_value = network(torch.flip(x, dims=(1,))).detach().numpy()
    assert not np.array_equal(original, reversed_value)


def test_hyperparameter_selection_uses_validation_and_fits_model() -> None:
    config, _, _, split = _fixture()
    selected, epoch, candidates = select_temporal_hyperparameters(
        "1s", split["train"], split["validation"], config
    )
    assert candidates
    assert 1 <= epoch <= selected.max_epochs
    model = fit_selected_temporal_model(
        "1s",
        selected,
        epoch,
        split["train"],
        split["validation"],
        split["calibration"],
        config,
    )
    predictions, raw, calibrated = prediction_rows(
        model, split["engineering_holdout"], config, "engineering_holdout"
    )
    assert len(predictions) == 400
    assert raw.rows == calibrated.rows == 400
    assert 0.0 <= calibrated.brier <= 1.0


def test_calibration_labels_do_not_change_raw_model() -> None:
    config, _, _, split = _fixture()
    selected, epoch, _ = select_temporal_hyperparameters(
        "250ms", split["train"], split["validation"], config
    )
    original = fit_selected_temporal_model(
        "250ms", selected, epoch, split["train"], split["validation"], split["calibration"], config
    )
    target_name = HORIZON_TARGETS["250ms"]
    changed_calibration = []
    for sequence in split["calibration"]:
        endpoint = sequence.endpoint
        labels = dict(endpoint.labels)
        labels[target_name] = 1 - labels[target_name]
        rows = (*sequence.rows[:-1], replace(endpoint, labels=labels))
        changed_calibration.append(replace(sequence, rows=rows))
    changed = fit_selected_temporal_model(
        "250ms", selected, epoch, split["train"], split["validation"], changed_calibration, config
    )
    x, _ = sequence_matrix(split["engineering_holdout"][:50], config, "250ms")
    assert np.array_equal(original.predict_uncalibrated(x), changed.predict_uncalibrated(x))
    assert not np.array_equal(original.predict_calibrated(x), changed.predict_calibrated(x))


def test_state_dict_json_roundtrip_preserves_predictions() -> None:
    config, _, _, split = _fixture()
    selected, epoch, candidates = select_temporal_hyperparameters(
        "5s", split["train"], split["validation"], config
    )
    model = fit_selected_temporal_model(
        "5s", selected, epoch, split["train"], split["validation"], split["calibration"], config
    )
    card = temporal_model_card(model, config, candidates)
    weights = state_dict_payload(model)
    loaded = load_model_from_payloads(card, weights, config)
    x, _ = sequence_matrix(split["engineering_holdout"][:30], config, "5s")
    assert np.array_equal(model.predict_calibrated(x), loaded.predict_calibrated(x))


def test_decision_proxy_is_fixed_and_not_selection_metric() -> None:
    config, _, _, split = _fixture()
    y = np.asarray([0, 1, 0, 1], dtype=np.int64)
    p = np.asarray([0.1, 0.9, 0.2, 0.8], dtype=np.float64)
    report = decision_proxy(y, p, config)
    assert report["aggressive_threshold"] == pytest.approx(0.35)
    assert report["mean_proxy_cost"] >= report["oracle_mean_proxy_cost"]
    baseline = base_rate_proxy(split["engineering_holdout"], "1s", 0.5, config)
    assert baseline["rows"] == 400
    assert not config.use_decision_proxy_for_selection


def test_ood_and_temporal_order_ablation_are_diagnostic_only() -> None:
    config, _, _, split = _fixture()
    selected, epoch, _ = select_temporal_hyperparameters(
        "1s", split["train"], split["validation"], config
    )
    model = fit_selected_temporal_model(
        "1s", selected, epoch, split["train"], split["validation"], split["calibration"], config
    )
    diagnostic = ood_diagnostics(model, split["engineering_holdout"], config)
    assert diagnostic["status"] == "synthetic_engineering_perturbations_not_generalisation_claim"
    assert diagnostic["mean_abs_probability_shift_feature_stress"] > 0.0
    assert diagnostic["mean_abs_probability_shift_temporal_reversal"] > 0.0
    reversed_sequences = reverse_sequences(split["engineering_holdout"][:5])
    assert [item.endpoint.row_id for item in reversed_sequences] == [
        item.endpoint.row_id for item in split["engineering_holdout"][:5]
    ]


def test_config_rejects_architecture_and_selection_drift(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    cases = [
        ("architecture", "transformer"),
        ("selected_horizon", "1s"),
        ("final_model_selection_allowed", True),
        ("use_engineering_holdout_for_selection", True),
        ("use_decision_proxy_for_selection", True),
        ("sequence_length", 99),
        ("conv_kernel_size", 99),
    ]
    for field, value in cases:
        changed = dict(raw)
        changed[field] = value
        path = tmp_path / f"bad-{field}.json"
        path.write_text(json.dumps(changed))
        with pytest.raises(TemporalModelError):
            load_temporal_model_config(path)


def test_sequence_builder_rejects_missing_source_row() -> None:
    config, rows, _, _ = _fixture()
    with pytest.raises(TemporalModelError, match="incomplete or reordered"):
        build_sequences(rows[:-1], config)


def test_fixture_write_verify_rerun_and_tamper(tmp_path: Path) -> None:
    config = _config()
    first = write_temporal_model_fixture(config, tmp_path / "a")
    second = write_temporal_model_fixture(config, tmp_path / "b")
    assert verify_temporal_model_fixture(first, config) == {
        "status": "ok",
        "source_rows": 4800,
        "sequences": 2000,
        "models": 3,
        "horizons": 3,
    }
    assert (first.parent / "report.json").read_bytes() == (
        second.parent / "report.json"
    ).read_bytes()
    first_manifest = json.loads(first.read_text())
    second_manifest = json.loads(second.read_text())
    first_hashes = {item["relative_path"]: item["sha256"] for item in first_manifest["artifacts"]}
    second_hashes = {item["relative_path"]: item["sha256"] for item in second_manifest["artifacts"]}
    assert first_hashes == second_hashes
    weights = first.parent / "models/1s/causal_conv1d_lstm/weights.json"
    original = weights.read_text()
    weights.write_text(original + " ")
    with pytest.raises(TemporalModelError, match="artifact verification"):
        verify_temporal_model_fixture(first, config)


def test_additional_config_failure_paths(tmp_path: Path) -> None:
    raw = json.loads(CONFIG.read_text())
    cases: list[tuple[str, object]] = [
        ("schema_version", "bad"),
        ("symbols", ["BTCUSDT"]),
        ("feature_names", raw["feature_names"][:-1]),
        ("candidate_horizons", ["1s"]),
        ("mode", "bad"),
        ("split_days", []),
        ("calibration_method", "isotonic"),
        ("random_seed", -1),
        ("precision_recall_thresholds", []),
        ("precision_recall_thresholds", [0.5, 0.5]),
        ("hyperparameters", []),
        ("decision_proxy", []),
        ("ood_feature_stress", []),
    ]
    for index, (field, value) in enumerate(cases):
        changed = dict(raw)
        changed[field] = value
        path = tmp_path / f"bad-extra-{index}.json"
        path.write_text(json.dumps(changed))
        with pytest.raises(TemporalModelError):
            load_temporal_model_config(path)

    bad_split = dict(raw)
    bad_split["split_days"] = {**raw["split_days"], "train": 49}
    path = tmp_path / "bad-split-counts.json"
    path.write_text(json.dumps(bad_split))
    with pytest.raises(TemporalModelError):
        load_temporal_model_config(path)

    bad_hyper = dict(raw)
    bad_hyper["hyperparameters"] = [{**raw["hyperparameters"][0], "patience": 14}]
    path = tmp_path / "bad-patience.json"
    path.write_text(json.dumps(bad_hyper))
    with pytest.raises(TemporalModelError):
        load_temporal_model_config(path)

    bad_proxy = dict(raw)
    bad_proxy["decision_proxy"] = {"aggressive_cost": 2.0, "passive_depletion_cost": 1.0}
    path = tmp_path / "bad-proxy.json"
    path.write_text(json.dumps(bad_proxy))
    with pytest.raises(TemporalModelError):
        load_temporal_model_config(path)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("[")
    with pytest.raises(TemporalModelError):
        load_temporal_model_config(malformed)

    non_object = tmp_path / "non-object.json"
    non_object.write_text("[]")
    with pytest.raises(TemporalModelError):
        load_temporal_model_config(non_object)
