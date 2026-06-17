"""Train the purchase-intent model and save portable artifacts.

The shipped model is trained WITHOUT PageValues so it learns from behavioral signals
rather than the dominant near-leakage feature. A comparison model WITH PageValues is
trained and evaluated in the same run to document the leakage, but is never saved. The
three saved artifacts (model.json, pipeline.joblib, feature_schema.json) all reflect the
without-PageValues model, and feature_schema.json lists only the shipped feature set.

The raw payload contract in src/core/schema.py is unchanged: payloads still carry
PageValues; the shipped model simply does not consume it.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from src.config import MODELS_DIR, RANDOM_STATE
from src.core.db import load_features
from src.core.features import (
    BOOLEAN_FEATURE_COLUMNS,
    CATEGORICAL_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    prepare,
)
from src.core.schema import TARGET_COLUMN

# Dropped from the shipped model to avoid the dominant near-leakage signal.
EXCLUDED_FEATURES = ["PageValues"]

# Ordered shipped feature contract (canonical prepare order, minus the excluded set).
SHIPPED_FEATURE_COLUMNS = [c for c in FEATURE_COLUMNS if c not in EXCLUDED_FEATURES]
SHIPPED_NUMERIC_COLUMNS = [c for c in NUMERIC_FEATURE_COLUMNS if c not in EXCLUDED_FEATURES]

TEST_SIZE = 0.2


def build_estimator(numeric_cols, categorical_cols, boolean_cols, scale_pos_weight):
    """Build a preprocessing + XGBoost pipeline.

    Numerics and booleans pass through unscaled (XGBoost splits on thresholds and is
    scale-invariant, so a scaler would only add fitted state to persist and port).
    Categoricals are one-hot encoded so the booster receives numeric input.
    """
    preprocess = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", numeric_cols),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_cols),
            ("boolean", "passthrough", boolean_cols),
        ],
        remainder="drop",
    )
    classifier = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="aucpr",
        tree_method="hist",
        scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return Pipeline([("preprocess", preprocess), ("model", classifier)])


def evaluate(pipeline, features, target, label):
    """Print AUC-ROC and PR-AUC for a fitted pipeline on a holdout set."""
    proba = pipeline.predict_proba(features)[:, 1]
    auc = roc_auc_score(target, proba)
    pr_auc = average_precision_score(target, proba)
    print(f"  {label:<30} AUC-ROC={auc:.4f}  PR-AUC={pr_auc:.4f}")
    return auc, pr_auc


def print_importances(pipeline, top=15):
    """Print the top transformed-feature importances for the shipped model."""
    preprocess = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    names = preprocess.get_feature_names_out()
    ranked = sorted(zip(names, model.feature_importances_), key=lambda kv: kv[1], reverse=True)
    print("\nTop feature importances (shipped model, without PageValues):")
    for name, score in ranked[:top]:
        print(f"  {name:<34} {score:.4f}")


def save_artifacts(pipeline, train_features, scale_pos_weight):
    """Persist the shipped model natively, the preprocessing pipeline, and the schema."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model = pipeline.named_steps["model"]
    preprocess = pipeline.named_steps["preprocess"]

    model.save_model(str(MODELS_DIR / "model.json"))
    joblib.dump(preprocess, MODELS_DIR / "pipeline.joblib")

    schema = {
        "target": TARGET_COLUMN,
        "random_state": RANDOM_STATE,
        "excluded_features": EXCLUDED_FEATURES,
        "feature_columns": SHIPPED_FEATURE_COLUMNS,
        "dtypes": {col: str(train_features[col].dtype) for col in SHIPPED_FEATURE_COLUMNS},
        "numeric_features": SHIPPED_NUMERIC_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURE_COLUMNS,
        "boolean_features": BOOLEAN_FEATURE_COLUMNS,
        "model_artifact": "model.json",
        "preprocessing_artifact": "pipeline.joblib",
        "scale_pos_weight": round(float(scale_pos_weight), 6),
    }
    (MODELS_DIR / "feature_schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    print(f"\nSaved to {MODELS_DIR}: model.json, pipeline.joblib, feature_schema.json")


def verify_saved(pipeline, test_features):
    """Reload the saved artifacts and confirm they reproduce the trained scores.

    This exercises the exact chain the serving path uses (preprocessing pipeline then
    native booster), guarding against artifact drift before step 4 wires up predict().
    """
    preprocess = joblib.load(MODELS_DIR / "pipeline.joblib")
    booster = XGBClassifier()
    booster.load_model(str(MODELS_DIR / "model.json"))

    sample = test_features.head(5)
    reloaded = booster.predict_proba(preprocess.transform(sample))[:, 1]
    original = pipeline.predict_proba(sample)[:, 1]
    assert np.allclose(reloaded, original, atol=1e-6), "saved artifacts diverge from trained pipeline"
    print("Verified: reloaded artifacts reproduce the trained pipeline's scores.")


def main():
    frame = load_features()
    features = prepare(frame)
    target = frame[TARGET_COLUMN].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=TEST_SIZE, stratify=target, random_state=RANDOM_STATE
    )
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    print(
        f"Train rows={len(x_train)}, test rows={len(x_test)}, "
        f"scale_pos_weight={scale_pos_weight:.3f}"
    )
    print(f"Test positive rate (PR-AUC baseline)={y_test.mean():.4f}\n")

    shipped = build_estimator(
        SHIPPED_NUMERIC_COLUMNS, CATEGORICAL_FEATURE_COLUMNS, BOOLEAN_FEATURE_COLUMNS, scale_pos_weight
    )
    shipped.fit(x_train[SHIPPED_FEATURE_COLUMNS], y_train)

    comparison = build_estimator(
        NUMERIC_FEATURE_COLUMNS, CATEGORICAL_FEATURE_COLUMNS, BOOLEAN_FEATURE_COLUMNS, scale_pos_weight
    )
    comparison.fit(x_train[FEATURE_COLUMNS], y_train)

    print("Evaluation (test set):")
    evaluate(shipped, x_test[SHIPPED_FEATURE_COLUMNS], y_test, "shipped (without PageValues)")
    evaluate(comparison, x_test[FEATURE_COLUMNS], y_test, "comparison (with PageValues)")

    print_importances(shipped)
    save_artifacts(shipped, x_train[SHIPPED_FEATURE_COLUMNS], scale_pos_weight)
    verify_saved(shipped, x_test[SHIPPED_FEATURE_COLUMNS])


if __name__ == "__main__":
    main()
