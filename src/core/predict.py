"""Shared prediction function: predict(payload) -> {intent_score, next_best_action, drivers}.

This is the single scoring entry point. Both the local FastAPI app and the Cloudera
model deployment call it unchanged. It validates the payload against the raw schema,
prepares features with the shared prep, selects the shipped feature columns recorded in
models/feature_schema.json (PageValues is dropped here), scores with the saved
preprocessing pipeline plus the native booster, attaches the next-best-action, and
explains the score with per-session feature drivers. Artifacts load once and are cached.

Drivers are the model's own feature contributions (XGBoost pred_contribs, TreeSHAP-style)
in log-odds space. One-hot dummy columns are summed back to their source feature, so a
driver reads as a single signal (e.g. Month, VisitorType) rather than per-category dummies.
The sign gives direction: positive pushes the session toward a purchase, negative away.
"""
import json
from functools import lru_cache

import joblib
import xgboost as xgb
from xgboost import XGBClassifier

from src.config import MODELS_DIR
from src.core.features import prepare_payload
from src.core.nba import next_best_action
from src.core.schema import CATEGORICAL_COLUMNS

FEATURE_SCHEMA_PATH = MODELS_DIR / "feature_schema.json"
PREPROCESSING_PATH = MODELS_DIR / "pipeline.joblib"
MODEL_PATH = MODELS_DIR / "model.json"

DRIVER_COUNT = 6


def _source_feature(transformed_name: str) -> str:
    """Map a ColumnTransformer output name back to its raw source feature.

    e.g. 'numeric__ExitRates' -> 'ExitRates', 'boolean__Weekend' -> 'Weekend',
    'categorical__Month_Nov' -> 'Month'.
    """
    for prefix in ("numeric__", "boolean__"):
        if transformed_name.startswith(prefix):
            return transformed_name[len(prefix):]
    if transformed_name.startswith("categorical__"):
        rest = transformed_name[len("categorical__"):]
        for column in CATEGORICAL_COLUMNS:
            if rest == column or rest.startswith(column + "_"):
                return column
        return rest
    return transformed_name


def _native(value):
    """Convert a numpy/pandas scalar to a JSON-native Python scalar."""
    return value.item() if hasattr(value, "item") else value


@lru_cache(maxsize=1)
def _load_artifacts():
    """Load the schema, preprocessing pipeline, booster, and feature-name maps once."""
    missing = [p for p in (FEATURE_SCHEMA_PATH, PREPROCESSING_PATH, MODEL_PATH) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Model artifacts not found: {[str(p) for p in missing]}. "
            "Run src/train/train.py first."
        )
    schema = json.loads(FEATURE_SCHEMA_PATH.read_text())
    preprocess = joblib.load(PREPROCESSING_PATH)
    booster = XGBClassifier()
    booster.load_model(str(MODEL_PATH))
    feature_names = list(preprocess.get_feature_names_out())
    sources = [_source_feature(name) for name in feature_names]
    return schema, preprocess, booster, feature_names, sources


def _drivers(booster, feature_names, sources, transformed, prepared_row, top_n=DRIVER_COUNT):
    """Return the top per-feature contributions to this session's score."""
    dmatrix = xgb.DMatrix(transformed, feature_names=feature_names)
    # pred_contribs returns one value per feature plus a trailing bias term.
    contributions = booster.get_booster().predict(dmatrix, pred_contribs=True)[0]

    per_source = {}
    for index, source in enumerate(sources):
        per_source[source] = per_source.get(source, 0.0) + float(contributions[index])

    ranked = sorted(per_source.items(), key=lambda item: abs(item[1]), reverse=True)
    drivers = []
    for feature, contribution in ranked[:top_n]:
        drivers.append(
            {
                "feature": feature,
                "value": _native(prepared_row.get(feature)),
                "contribution": round(contribution, 4),
                "direction": "up" if contribution > 0 else "down",
            }
        )
    return drivers


def predict(payload: dict) -> dict:
    """Score one raw session payload: intent score, next-best-action, and drivers."""
    schema, preprocess, booster, feature_names, sources = _load_artifacts()

    prepared = prepare_payload(payload)
    prepared_row = prepared.iloc[0].to_dict()
    model_input = prepared[schema["feature_columns"]]
    transformed = preprocess.transform(model_input)
    score = float(booster.predict_proba(transformed)[:, 1][0])

    return {
        "intent_score": round(score, 4),
        "next_best_action": next_best_action(score, prepared_row),
        "drivers": _drivers(booster, feature_names, sources, transformed, prepared_row),
    }
