from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from robust_execution.prediction import (
    load_prediction_feature_config,
    verify_prediction_dataset,
    write_prediction_fixture,
)
from robust_execution.prediction.fixture import validation_fixture
from robust_execution.prediction.models import PredictionDataError

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/models/step21_causal_features_sample.json"


def _build(tmp_path: Path) -> Path:
    config = load_prediction_feature_config(CONFIG)
    events, decisions, coverage = validation_fixture()
    return write_prediction_fixture(config, events, decisions, coverage, tmp_path)


def test_prediction_artifact_roundtrip_and_schemas(tmp_path: Path) -> None:
    manifest_path = _build(tmp_path)
    assert verify_prediction_dataset(manifest_path) == {
        "status": "ok",
        "rows": 8,
        "features": 20,
        "tables": 2,
    }
    manifest = json.loads(manifest_path.read_text())
    dictionary = json.loads((manifest_path.parent / "feature-dictionary.json").read_text())
    manifest_schema = json.loads(
        (ROOT / "schemas/prediction/prediction-dataset-manifest-v1.schema.json").read_text()
    )
    dictionary_schema = json.loads(
        (ROOT / "schemas/prediction/feature-dictionary-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(manifest_schema).validate(manifest)
    jsonschema.Draft202012Validator(dictionary_schema).validate(dictionary)


def test_prediction_artifact_is_immutable_and_deterministic(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = _build(first_root)
    second = _build(second_root)
    assert first.read_bytes() == second.read_bytes()
    for relative in (
        "feature-dictionary.json",
        "input-events.json",
        "tables/prediction_features/columns.json.gz",
        "tables/prediction_labels/columns.json.gz",
    ):
        assert (first.parent / relative).read_bytes() == (second.parent / relative).read_bytes()
    config = load_prediction_feature_config(CONFIG)
    events, decisions, coverage = validation_fixture()
    with pytest.raises(FileExistsError):
        write_prediction_fixture(config, events, decisions, coverage, first_root)


@pytest.mark.parametrize(
    "target",
    ["feature-dictionary.json", "input-events.json", "dataset-manifest.sha256.json"],
)
def test_verifier_rejects_tampering(tmp_path: Path, target: str) -> None:
    manifest_path = _build(tmp_path)
    path = manifest_path.parent / target
    if target.endswith(".json"):
        obj = json.loads(path.read_text())
        obj["tampered"] = True
        path.write_text(json.dumps(obj))
    with pytest.raises((PredictionDataError, KeyError, json.JSONDecodeError)):
        verify_prediction_dataset(manifest_path)


def test_verifier_rejects_feature_table_tamper(tmp_path: Path) -> None:
    manifest_path = _build(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    item = next(item for item in manifest["tables"] if item["table_name"] == "prediction_features")
    path = manifest_path.parent / item["data_relative_path"]
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(PredictionDataError, match="data hash"):
        verify_prediction_dataset(manifest_path)
