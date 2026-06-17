"""Shared feature preparation used at BOTH train and serve, so there is no skew.

`prepare` is stateless and fully vectorized: it applies the same row-local arithmetic
whether handed a full training batch or a single-row payload, so per-row output is
identical either way (asserted by tests/test_feature_parity.py). It holds NO fitted
state. Every fitted transform (categorical encoding, scaling, imputation) lives in the
sklearn pipeline saved at train time and is loaded, never recomputed, at serve time.
"""
import pandas as pd

from src.core.schema import (
    BOOL_COLUMNS,
    CATEGORICAL_COLUMNS,
    FLOAT_COLUMNS,
    INT_COLUMNS,
    RAW_FEATURE_COLUMNS,
    coerce_dtypes,
    validate_payload,
)

# Deterministic, row-local derived features (no cross-row aggregation, no fitted state).
DERIVED_FEATURE_COLUMNS = ["total_pages", "total_duration", "avg_product_duration"]

# Ordered model-input columns produced by prepare().
FEATURE_COLUMNS = RAW_FEATURE_COLUMNS + DERIVED_FEATURE_COLUMNS

# Column groups for the train-time pipeline's ColumnTransformer.
NUMERIC_FEATURE_COLUMNS = INT_COLUMNS + FLOAT_COLUMNS + DERIVED_FEATURE_COLUMNS
CATEGORICAL_FEATURE_COLUMNS = list(CATEGORICAL_COLUMNS)
BOOLEAN_FEATURE_COLUMNS = list(BOOL_COLUMNS)


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive the ordered model-input features from raw session rows.

    Accepts a batch or single-row DataFrame containing the raw feature columns and
    returns a DataFrame of FEATURE_COLUMNS. Stateless and vectorized: identical per-row
    output for batch and single-row inputs.
    """
    base = coerce_dtypes(frame.loc[:, RAW_FEATURE_COLUMNS].copy())

    base["total_pages"] = (
        base["Administrative"] + base["Informational"] + base["ProductRelated"]
    )
    base["total_duration"] = (
        base["Administrative_Duration"]
        + base["Informational_Duration"]
        + base["ProductRelated_Duration"]
    )
    product_pages = base["ProductRelated"].astype("float64")
    avg_product_duration = base["ProductRelated_Duration"] / product_pages.where(product_pages != 0)
    base["avg_product_duration"] = avg_product_duration.fillna(0.0)

    return base.loc[:, FEATURE_COLUMNS]


def prepare_payload(payload: dict) -> pd.DataFrame:
    """Validate a raw session payload, then prepare it as a single model-input row."""
    clean = validate_payload(payload)
    return prepare(pd.DataFrame([clean]))
