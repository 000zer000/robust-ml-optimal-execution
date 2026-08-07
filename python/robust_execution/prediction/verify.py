"""Independent verification for Step 21 prediction-data artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from robust_execution.historical_replay.tables import read_table
from robust_execution.prediction.artifacts import FEATURE_NAMES
from robust_execution.prediction.models import PredictionDataError


def verify_prediction_dataset(manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "prediction-dataset-manifest-v1"
    ):
        raise PredictionDataError("prediction manifest schema is invalid")
    if manifest.get("step") != 21 or manifest.get("research_admissible") is not False:
        raise PredictionDataError("Step 21 validation dataset research boundary changed")
    if manifest.get("features_and_labels_physically_separated") is not True:
        raise PredictionDataError("features and labels must remain physically separated")
    if manifest.get("future_information_used_in_features") is not False:
        raise PredictionDataError("prediction manifest claims future feature information")
    if manifest.get("exact_historical_queue_used") is not False:
        raise PredictionDataError("exact historical queue usage is forbidden")
    if manifest.get("selected_horizon") != "PRE_DATA_FIELD_BEFORE_CALIBRATION":
        raise PredictionDataError("Step 21 cannot select the primary horizon")
    root = manifest_path.parent
    input_path = root / "input-events.json"
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != manifest.get("input_events_sha256"):
        raise PredictionDataError("prediction input fixture hash mismatch")
    dictionary_path = root / "feature-dictionary.json"
    if hashlib.sha256(dictionary_path.read_bytes()).hexdigest() != manifest.get(
        "feature_dictionary_sha256"
    ):
        raise PredictionDataError("feature dictionary hash mismatch")
    dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
    if (
        dictionary.get("feature_names") != list(FEATURE_NAMES)
        or dictionary.get("all_features_causal") is not True
    ):
        raise PredictionDataError("feature dictionary contract changed")
    tables = {
        item["table_name"]: item
        for item in manifest.get("tables", [])
        if isinstance(item, dict)
    }
    if set(tables) != {"prediction_features", "prediction_labels"}:
        raise PredictionDataError(
            "prediction dataset must contain exactly feature and label tables"
        )
    loaded: dict[str, list[dict[str, Any]]] = {}
    for name, item in tables.items():
        data_path = root / str(item["data_relative_path"])
        schema_path = root / str(item["schema_relative_path"])
        if hashlib.sha256(data_path.read_bytes()).hexdigest() != item["data_sha256"]:
            raise PredictionDataError(f"{name} data hash mismatch")
        if hashlib.sha256(schema_path.read_bytes()).hexdigest() != item["schema_sha256"]:
            raise PredictionDataError(f"{name} schema hash mismatch")
        loaded[name] = read_table(root, str(item["data_relative_path"]))
    features = loaded["prediction_features"]
    labels = loaded["prediction_labels"]
    if len(features) != len(labels) or len(features) != int(manifest["row_count"]):
        raise PredictionDataError("prediction feature/label row counts differ")
    feature_ids = [str(row["row_id"]) for row in features]
    label_ids = [str(row["row_id"]) for row in labels]
    if feature_ids != label_ids or len(set(feature_ids)) != len(feature_ids):
        raise PredictionDataError("feature/label row IDs differ or duplicate")
    for row in features:
        if int(row["maximum_source_event_time_ns"]) > int(row["source_cutoff_ns"]):
            raise PredictionDataError("feature source event exceeds source cutoff")
        if int(row["maximum_source_available_time_ns"]) > int(row["decision_time_ns"]):
            raise PredictionDataError("feature source event was unavailable at decision time")
        if not set(FEATURE_NAMES).issubset(row):
            raise PredictionDataError("feature row lacks frozen feature set")
    for row in labels:
        if int(row["target_start_exclusive_ns"]) >= int(row["label_coverage_end_ns"]):
            raise PredictionDataError("label coverage is invalid")
        for suffix in ("250ms", "1s", "5s"):
            if int(row[f"quote_depletion_{suffix}"]) not in {0, 1}:
                raise PredictionDataError("quote-depletion labels must be binary")
    sidecar = json.loads((root / "dataset-manifest.sha256.json").read_text(encoding="utf-8"))
    if not isinstance(sidecar, dict) or set(sidecar) != {"sha256"}:
        raise PredictionDataError("prediction manifest sidecar schema changed")
    if sidecar.get("sha256") != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise PredictionDataError("prediction manifest sidecar mismatch")
    return {"status": "ok", "rows": len(features), "features": len(FEATURE_NAMES), "tables": 2}
