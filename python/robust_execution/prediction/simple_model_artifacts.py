"""Immutable Step 22 simple-model engineering artifacts."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import sklearn

from robust_execution import __version__
from robust_execution.canonical_data.models import TableArtifact, write_columnar_table
from robust_execution.data_capture.storage import write_immutable_json
from robust_execution.historical_replay.tables import read_table
from robust_execution.prediction.simple_models import (
    HORIZON_TARGETS,
    FittedSimpleModel,
    SimpleModelConfig,
    SimpleModelError,
    TrainingRow,
    canonical_config_sha256,
    fit_selected_model,
    generate_engineering_training_rows,
    load_serialized_model,
    model_card,
    prediction_rows,
    reliability_bins,
    select_hyperparameters,
    serialize_model,
    slice_metrics,
    split_for_day,
)

FAMILIES = ("base_rate", "logistic", "gradient_boosted_trees", "simple_mlp")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema(name: str, columns: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "table_name": name,
        "columns": [
            {"name": column, "logical_type": "json_scalar", "nullable": False}
            for column in columns
        ],
    }


def _training_table_rows(
    rows: list[TrainingRow], config: SimpleModelConfig
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        result.append(
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
    return result


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
        _artifact_entry(
            manifest_root, table_root / artifact.schema_relative_path, "table_schema"
        ),
        _artifact_entry(
            manifest_root, table_root / artifact.data_relative_path, "table_data"
        ),
    ]


def write_simple_model_fixture(config: SimpleModelConfig, output_root: Path) -> Path:
    if config.mode != "engineering_fixture":
        raise SimpleModelError(
            "Step 22 committed fixture must remain engineering_fixture mode"
        )
    target = output_root / config.dataset_id
    if target.exists():
        raise FileExistsError(f"Step 22 model dataset already exists: {target}")
    target.mkdir(parents=True)
    rows = generate_engineering_training_rows(config)
    split_rows = {
        name: [row for row in rows if split_for_day(row.day_index, config.split_days) == name]
        for name in ("train", "validation", "calibration", "engineering_holdout")
    }
    config_snapshot = target / "training-config.json"
    write_immutable_json(config_snapshot, asdict(config))
    split_manifest = target / "split-manifest.json"
    write_immutable_json(
        split_manifest,
        {
            "schema_version": "simple-model-split-manifest-v1",
            "split_unit": "whole_synthetic_day",
            "chronological": True,
            "days": asdict(config.split_days),
            "rows": {name: len(value) for name, value in split_rows.items()},
            "symbols": list(config.symbols),
            "research_locked_test_opened": False,
        },
    )
    flat_rows = _training_table_rows(rows, config)
    row_columns = tuple(flat_rows[0])
    training_artifact = write_columnar_table(
        target,
        "engineering_training_rows",
        flat_rows,
        _schema("engineering_training_rows", row_columns),
        row_columns,
    )
    report_models: dict[str, Any] = {}
    artifact_entries: list[dict[str, object]] = [
        _artifact_entry(target, config_snapshot, "config"),
        _artifact_entry(target, split_manifest, "split_manifest"),
        *_table_entries(target, target, training_artifact),
    ]
    for horizon in config.candidate_horizons:
        report_models[horizon] = {}
        for family in FAMILIES:
            selected, candidates = select_hyperparameters(
                family,  # type: ignore[arg-type]
                horizon,
                split_rows["train"],
                split_rows["validation"],
                config,
            )
            model = fit_selected_model(
                family,  # type: ignore[arg-type]
                horizon,
                selected,
                split_rows["train"],
                split_rows["validation"],
                split_rows["calibration"],
                config,
            )
            model_root = target / "models" / horizon / family
            model_path = model_root / "model.pkl"
            serialize_model(model, model_path)
            card_path = model_root / "model-card.json"
            write_immutable_json(card_path, model_card(model, config, candidates))
            predictions, raw_metrics, calibrated_metrics = prediction_rows(
                model,
                split_rows["engineering_holdout"],
                config,
                "engineering_holdout",
            )
            prediction_columns = tuple(predictions[0])
            prediction_artifact = write_columnar_table(
                model_root,
                "engineering_holdout_predictions",
                predictions,
                _schema("engineering_holdout_predictions", prediction_columns),
                prediction_columns,
            )
            x_holdout = np.asarray(
                [
                    [row.feature[name] for name in config.feature_names]
                    for row in split_rows["engineering_holdout"]
                ],
                dtype=np.float64,
            )
            y_holdout = np.asarray(
                [row.labels[HORIZON_TARGETS[horizon]] for row in split_rows["engineering_holdout"]],
                dtype=np.int64,
            )
            calibrated_probability = model.predict_calibrated(x_holdout)
            reliability_path = model_root / "reliability.json"
            write_immutable_json(
                reliability_path,
                {
                    "schema_version": "reliability-diagram-v1",
                    "bins": reliability_bins(y_holdout, calibrated_probability, config.ece_bins),
                },
            )
            slices_path = model_root / "slice-metrics.json"
            write_immutable_json(
                slices_path,
                slice_metrics(model, split_rows["engineering_holdout"], config),
            )
            report_models[horizon][family] = {
                "selected_hyperparameters": selected,
                "uncalibrated_engineering_holdout": asdict(raw_metrics),
                "calibrated_engineering_holdout": asdict(calibrated_metrics),
                "model_card_sha256": _sha256(card_path),
                "prediction_data_sha256": prediction_artifact.data_sha256,
                "reliability_sha256": _sha256(reliability_path),
                "slice_metrics_sha256": _sha256(slices_path),
            }
            artifact_entries.extend(
                [
                    _artifact_entry(target, model_path, "trusted_pickle_model"),
                    _artifact_entry(target, card_path, "model_card"),
                    *_table_entries(target, model_root, prediction_artifact),
                    _artifact_entry(target, reliability_path, "reliability"),
                    _artifact_entry(target, slices_path, "slice_metrics"),
                ]
            )
    report_path = target / "report.json"
    write_immutable_json(
        report_path,
        {
            "schema_version": "simple-model-engineering-report-v1",
            "step": 22,
            "dataset_id": config.dataset_id,
            "software_version": __version__,
            "numpy_version": np.__version__,
            "sklearn_version": sklearn.__version__,
            "research_status": "synthetic_validation_only_non_research",
            "primary_horizon_selected": False,
            "final_model_family_selected": False,
            "controller_decision_value_used_for_horizon_selection": False,
            "locked_research_test_opened": False,
            "candidate_horizons": list(config.candidate_horizons),
            "families": list(FAMILIES),
            "row_count": len(rows),
            "split_rows": {name: len(value) for name, value in split_rows.items()},
            "models": report_models,
        },
    )
    artifact_entries.append(_artifact_entry(target, report_path, "report"))
    manifest_path = target / "dataset-manifest.json"
    write_immutable_json(
        manifest_path,
        {
            "schema_version": "simple-model-dataset-manifest-v1",
            "step": 22,
            "dataset_id": config.dataset_id,
            "software_version": __version__,
            "config_sha256": canonical_config_sha256(config),
            "step21_feature_contract_sha256": hashlib.sha256(
                (
                    Path(__file__).resolve().parents[3]
                    / "data/sample/prediction/step21-prediction-validation/feature-dictionary.json"
                ).read_bytes()
            ).hexdigest(),
            "research_status": "synthetic_validation_only_non_research",
            "row_count": len(rows),
            "model_count": len(config.candidate_horizons) * len(FAMILIES),
            "model_binary_byte_determinism_required": False,
            "semantic_prediction_determinism_required": True,
            "artifacts": artifact_entries,
        },
    )
    return manifest_path


def _reconstruct_rows(
    table_rows: list[dict[str, object]], config: SimpleModelConfig
) -> list[TrainingRow]:
    rows: list[TrainingRow] = []
    for raw in table_rows:
        feature = {name: int(raw[name]) for name in config.feature_names}
        labels = {target: int(raw[target]) for target in HORIZON_TARGETS.values()}
        rows.append(
            TrainingRow(
                row_id=str(raw["row_id"]),
                symbol=str(raw["symbol"]),
                passive_side=str(raw["passive_side"]),  # type: ignore[arg-type]
                day_index=int(raw["day_index"]),
                decision_index=int(raw["decision_index"]),
                feature=feature,
                labels=labels,
            )
        )
    return rows


def verify_simple_model_fixture(
    manifest_path: Path, config: SimpleModelConfig
) -> dict[str, object]:
    root = manifest_path.parent
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimpleModelError(f"cannot read Step 22 manifest: {exc}") from exc
    if (
        manifest.get("schema_version") != "simple-model-dataset-manifest-v1"
        or manifest.get("step") != 22
    ):
        raise SimpleModelError("Step 22 manifest identity changed")
    if manifest.get("research_status") != "synthetic_validation_only_non_research":
        raise SimpleModelError("Step 22 research boundary changed")
    if manifest.get("config_sha256") != canonical_config_sha256(config):
        raise SimpleModelError("Step 22 config hash mismatch")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise SimpleModelError("Step 22 artifact list is malformed")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise SimpleModelError("Step 22 artifact entry is malformed")
        path = root / str(artifact.get("relative_path"))
        if not path.is_file() or _sha256(path) != artifact.get("sha256"):
            raise SimpleModelError(f"Step 22 artifact verification failed: {path}")
    table_rows = read_table(root, "tables/engineering_training_rows/columns.json.gz")
    rows = _reconstruct_rows(table_rows, config)
    if len(rows) != manifest.get("row_count"):
        raise SimpleModelError("Step 22 training row count mismatch")
    holdout = [
        row
        for row in rows
        if split_for_day(row.day_index, config.split_days) == "engineering_holdout"
    ]
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    if (
        report.get("primary_horizon_selected") is not False
        or report.get("final_model_family_selected") is not False
    ):
        raise SimpleModelError("Step 22 may not select the research horizon/model family")
    if report.get("locked_research_test_opened") is not False:
        raise SimpleModelError("Step 22 fixture may not open the locked research test")
    checked = 0
    for horizon in config.candidate_horizons:
        for family in FAMILIES:
            model_root = root / "models" / horizon / family
            model = load_serialized_model(model_root / "model.pkl")
            if model.horizon != horizon or model.family != family:
                raise SimpleModelError("serialized model identity changed")
            x = np.asarray(
                [[row.feature[name] for name in config.feature_names] for row in holdout],
                dtype=np.float64,
            )
            recomputed = model.predict_calibrated(x)
            stored = read_table(
                model_root, "tables/engineering_holdout_predictions/columns.json.gz"
            )
            if len(stored) != len(holdout):
                raise SimpleModelError("prediction table row count changed")
            for expected, actual in zip(stored, recomputed, strict=True):
                if abs(float(expected["calibrated_probability"]) - float(actual)) > 1e-12:
                    raise SimpleModelError("stored prediction differs from serialized model")
            checked += 1
    return {
        "status": "ok",
        "rows": len(rows),
        "models": checked,
        "horizons": len(config.candidate_horizons),
    }
