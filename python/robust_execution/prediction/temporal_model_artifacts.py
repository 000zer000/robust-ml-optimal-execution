"""Immutable Step 23 temporal-model engineering artifacts and verifier."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from robust_execution import __version__
from robust_execution.canonical_data.models import TableArtifact, write_columnar_table
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.historical_replay.tables import read_table
from robust_execution.prediction.simple_models import HORIZON_TARGETS, TrainingRow, split_for_day
from robust_execution.prediction.temporal_models import (
    TemporalModelConfig,
    TemporalModelError,
    TemporalSequence,
    base_rate_proxy,
    build_sequences,
    canonical_config_sha256,
    decision_proxy,
    fit_selected_temporal_model,
    generate_temporal_training_rows,
    load_model_from_payloads,
    ood_diagnostics,
    prediction_rows,
    select_temporal_hyperparameters,
    sequence_matrix,
    sequence_reliability,
    slice_metrics,
    split_sequences,
    state_dict_payload,
    temporal_model_card,
)

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise ImportError("Step 23 artifact generation requires torch") from exc


FAMILY = "causal_conv1d_lstm"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema(name: str, columns: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "table_name": name,
        "columns": [
            {"name": column, "logical_type": "json_scalar", "nullable": False} for column in columns
        ],
    }


def _artifact_entry(root: Path, path: Path, kind: str) -> dict[str, object]:
    return {
        "kind": kind,
        "relative_path": str(path.relative_to(root)),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _table_entries(
    manifest_root: Path, table_root: Path, artifact: TableArtifact
) -> list[dict[str, object]]:
    return [
        _artifact_entry(manifest_root, table_root / artifact.schema_relative_path, "table_schema"),
        _artifact_entry(manifest_root, table_root / artifact.data_relative_path, "table_data"),
    ]


def _training_rows(rows: list[TrainingRow], config: TemporalModelConfig) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        output.append(
            {
                "row_id": row.row_id,
                "symbol": row.symbol,
                "passive_side": row.passive_side,
                "day_index": row.day_index,
                "decision_index": row.decision_index,
                "split": split_for_day(row.day_index, config.split_days),
                **row.feature,
                **row.labels,
            }
        )
    return output


def _sequence_rows(
    sequences: list[TemporalSequence], config: TemporalModelConfig
) -> list[dict[str, object]]:
    return [
        {
            "sequence_id": item.sequence_id,
            "symbol": item.symbol,
            "passive_side": item.passive_side,
            "day_index": item.day_index,
            "start_decision_index": item.start_decision_index,
            "end_decision_index": item.end_decision_index,
            "endpoint_row_id": item.endpoint.row_id,
            "split": split_for_day(item.day_index, config.split_days),
        }
        for item in sequences
    ]


def _decision_report(
    model: Any,
    sequences: list[TemporalSequence],
    config: TemporalModelConfig,
) -> dict[str, object]:
    x, y = sequence_matrix(sequences, config, model.horizon)
    calibrated = model.predict_calibrated(x)
    return {
        "status": "fixed_engineering_proxy_not_controller_value",
        "model": decision_proxy(y, calibrated, config),
        "training_base_rate": base_rate_proxy(
            sequences, model.horizon, model.train_prevalence, config
        ),
        "selection_use": False,
    }


def write_temporal_model_fixture(config: TemporalModelConfig, output_root: Path) -> Path:
    if config.mode != "engineering_fixture":
        raise TemporalModelError("committed Step 23 fixture must remain engineering_fixture mode")
    target = output_root / config.dataset_id
    if target.exists():
        raise FileExistsError(f"Step 23 temporal dataset already exists: {target}")
    target.mkdir(parents=True)
    rows = generate_temporal_training_rows(config)
    sequences = build_sequences(rows, config)
    split = split_sequences(sequences, config)

    config_path = target / "training-config.json"
    write_immutable_json(config_path, asdict(config))
    split_path = target / "split-manifest.json"
    write_immutable_json(
        split_path,
        {
            "schema_version": "temporal-model-split-manifest-v1",
            "split_unit": "whole_synthetic_day",
            "chronological": True,
            "days": asdict(config.split_days),
            "source_rows": {
                name: len(
                    [row for row in rows if split_for_day(row.day_index, config.split_days) == name]
                )
                for name in split
            },
            "sequences": {name: len(values) for name, values in split.items()},
            "sequence_length": config.sequence_length,
            "sequence_stride": config.sequence_stride,
            "sequence_crosses_day": False,
            "sequence_crosses_symbol": False,
            "sequence_crosses_side": False,
            "research_locked_test_opened": False,
        },
    )
    training_flat = _training_rows(rows, config)
    training_columns = tuple(training_flat[0])
    training_artifact = write_columnar_table(
        target,
        "engineering_training_rows",
        training_flat,
        _schema("engineering_training_rows", training_columns),
        training_columns,
    )
    sequence_flat = _sequence_rows(sequences, config)
    sequence_columns = tuple(sequence_flat[0])
    sequence_artifact = write_columnar_table(
        target,
        "engineering_sequences",
        sequence_flat,
        _schema("engineering_sequences", sequence_columns),
        sequence_columns,
    )
    artifact_entries: list[dict[str, object]] = [
        _artifact_entry(target, config_path, "config"),
        _artifact_entry(target, split_path, "split_manifest"),
        *_table_entries(target, target, training_artifact),
        *_table_entries(target, target, sequence_artifact),
    ]
    reports: dict[str, object] = {}
    for horizon in config.candidate_horizons:
        selected, best_epoch, candidates = select_temporal_hyperparameters(
            horizon, split["train"], split["validation"], config
        )
        model = fit_selected_temporal_model(
            horizon,
            selected,
            best_epoch,
            split["train"],
            split["validation"],
            split["calibration"],
            config,
        )
        model_root = target / "models" / horizon / FAMILY
        card_path = model_root / "model-card.json"
        weights_path = model_root / "weights.json"
        write_immutable_json(card_path, temporal_model_card(model, config, candidates))
        write_immutable_json(weights_path, state_dict_payload(model))
        predictions, raw_metrics, calibrated_metrics = prediction_rows(
            model, split["engineering_holdout"], config, "engineering_holdout"
        )
        prediction_columns = tuple(predictions[0])
        prediction_artifact = write_columnar_table(
            model_root,
            "engineering_holdout_predictions",
            predictions,
            _schema("engineering_holdout_predictions", prediction_columns),
            prediction_columns,
        )
        reliability_path = model_root / "reliability.json"
        write_immutable_json(
            reliability_path,
            {
                "schema_version": "reliability-diagram-v1",
                "bins": sequence_reliability(model, split["engineering_holdout"], config),
            },
        )
        slices_path = model_root / "slice-metrics.json"
        write_immutable_json(
            slices_path, slice_metrics(model, split["engineering_holdout"], config)
        )
        ood_path = model_root / "ood-diagnostics.json"
        write_immutable_json(ood_path, ood_diagnostics(model, split["engineering_holdout"], config))
        decision_path = model_root / "decision-proxy.json"
        write_immutable_json(
            decision_path, _decision_report(model, split["engineering_holdout"], config)
        )
        reports[horizon] = {
            "selected_hyperparameters": asdict(selected),
            "selected_epoch": best_epoch,
            "parameter_count": sum(parameter.numel() for parameter in model.network.parameters()),
            "uncalibrated_engineering_holdout": asdict(raw_metrics),
            "calibrated_engineering_holdout": asdict(calibrated_metrics),
            "model_card_sha256": _sha256(card_path),
            "weights_sha256": _sha256(weights_path),
            "prediction_data_sha256": prediction_artifact.data_sha256,
            "reliability_sha256": _sha256(reliability_path),
            "slice_metrics_sha256": _sha256(slices_path),
            "ood_diagnostics_sha256": _sha256(ood_path),
            "decision_proxy_sha256": _sha256(decision_path),
        }
        artifact_entries.extend(
            [
                _artifact_entry(target, card_path, "model_card"),
                _artifact_entry(target, weights_path, "deterministic_model_weights"),
                *_table_entries(target, model_root, prediction_artifact),
                _artifact_entry(target, reliability_path, "reliability"),
                _artifact_entry(target, slices_path, "slice_metrics"),
                _artifact_entry(target, ood_path, "ood_diagnostics"),
                _artifact_entry(target, decision_path, "decision_proxy"),
            ]
        )
    report_path = target / "report.json"
    write_immutable_json(
        report_path,
        {
            "schema_version": "temporal-model-engineering-report-v1",
            "step": 23,
            "dataset_id": config.dataset_id,
            "software_version": __version__,
            "numpy_version": np.__version__,
            "torch_version": torch.__version__,
            "research_status": "synthetic_validation_only_non_research",
            "architecture": FAMILY,
            "architecture_count": 1,
            "candidate_horizons": list(config.candidate_horizons),
            "primary_horizon_selected": False,
            "final_model_family_selected": False,
            "engineering_holdout_used_for_selection": False,
            "decision_proxy_used_for_selection": False,
            "locked_research_test_opened": False,
            "step24_controller_integrated": False,
            "source_row_count": len(rows),
            "sequence_count": len(sequences),
            "split_sequences": {name: len(values) for name, values in split.items()},
            "models": reports,
        },
    )
    artifact_entries.append(_artifact_entry(target, report_path, "report"))
    manifest_path = target / "dataset-manifest.json"
    step21_dictionary = (
        Path(__file__).resolve().parents[3]
        / "data/sample/prediction/step21-prediction-validation/feature-dictionary.json"
    )
    write_immutable_json(
        manifest_path,
        {
            "schema_version": "temporal-model-dataset-manifest-v1",
            "step": 23,
            "dataset_id": config.dataset_id,
            "software_version": __version__,
            "config_sha256": canonical_config_sha256(config),
            "step21_feature_contract_sha256": hashlib.sha256(
                step21_dictionary.read_bytes()
            ).hexdigest(),
            "research_status": "synthetic_validation_only_non_research",
            "architecture": FAMILY,
            "source_row_count": len(rows),
            "sequence_count": len(sequences),
            "model_count": len(config.candidate_horizons),
            "semantic_prediction_determinism_required": True,
            "locked_research_test_opened": False,
            "artifacts": artifact_entries,
        },
    )
    return manifest_path


def _reconstruct_training_rows(
    flat: list[dict[str, object]], config: TemporalModelConfig
) -> list[TrainingRow]:
    rows: list[TrainingRow] = []
    for raw in flat:
        rows.append(
            TrainingRow(
                row_id=str(raw["row_id"]),
                symbol=str(raw["symbol"]),
                passive_side=str(raw["passive_side"]),  # type: ignore[arg-type]
                day_index=int(raw["day_index"]),
                decision_index=int(raw["decision_index"]),
                feature={name: int(raw[name]) for name in config.feature_names},
                labels={target: int(raw[target]) for target in HORIZON_TARGETS.values()},
            )
        )
    return rows


def verify_temporal_model_fixture(
    manifest_path: Path, config: TemporalModelConfig
) -> dict[str, object]:
    root = manifest_path.parent
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemporalModelError(f"cannot read Step 23 manifest: {exc}") from exc
    if (
        manifest.get("schema_version") != "temporal-model-dataset-manifest-v1"
        or manifest.get("step") != 23
    ):
        raise TemporalModelError("Step 23 manifest identity changed")
    if manifest.get("research_status") != "synthetic_validation_only_non_research":
        raise TemporalModelError("Step 23 research boundary changed")
    if manifest.get("config_sha256") != canonical_config_sha256(config):
        raise TemporalModelError("Step 23 config hash mismatch")
    if manifest.get("architecture") != FAMILY or manifest.get("model_count") != 3:
        raise TemporalModelError("Step 23 architecture/model count changed")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise TemporalModelError("Step 23 artifact list is malformed")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise TemporalModelError("Step 23 artifact entry malformed")
        path = root / str(artifact.get("relative_path"))
        if not path.is_file() or _sha256(path) != artifact.get("sha256"):
            raise TemporalModelError(f"Step 23 artifact verification failed: {path}")
    flat = read_table(root, "tables/engineering_training_rows/columns.json.gz")
    rows = _reconstruct_training_rows(flat, config)
    sequences = build_sequences(rows, config)
    split = split_sequences(sequences, config)
    if len(rows) != manifest.get("source_row_count") or len(sequences) != manifest.get(
        "sequence_count"
    ):
        raise TemporalModelError("Step 23 row/sequence count mismatch")
    json.loads((root / "report.json").read_text())
    for horizon in config.candidate_horizons:
        model_root = root / "models" / horizon / FAMILY
        card = json.loads((model_root / "model-card.json").read_text())
        weights = json.loads((model_root / "weights.json").read_text())
        model = load_model_from_payloads(card, weights, config)
        x, _ = sequence_matrix(split["engineering_holdout"], config, horizon)
        current = model.predict_calibrated(x)
        predictions = read_table(
            model_root, "tables/engineering_holdout_predictions/columns.json.gz"
        )
        stored = np.asarray(
            [float(item["calibrated_probability"]) for item in predictions], dtype=np.float64
        )
        # Reconstructed float32 Torch inference can differ by a few final bits across CPU
        # kernels. The tolerance is far below the precision used by any decision threshold.
        if not np.allclose(current, stored, rtol=1e-6, atol=2e-7):
            maximum_error = float(np.max(np.abs(current - stored)))
            raise TemporalModelError(
                f"Step 23 semantic prediction mismatch for {horizon}: "
                f"maximum absolute error {maximum_error}"
            )
    return {
        "status": "ok",
        "source_rows": len(rows),
        "sequences": len(sequences),
        "models": len(config.candidate_horizons),
        "horizons": len(config.candidate_horizons),
    }
