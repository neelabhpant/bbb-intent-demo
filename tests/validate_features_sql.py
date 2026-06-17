"""Validate sql/features.sql on DuckDB against the local Parquet table.

Run as a standalone script (python tests/validate_features_sql.py) or via pytest.
Confirms the portable query returns the full, correctly-shaped, null-free feature
source that training and serving depend on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.db import load_features
from src.core.schema import ALL_COLUMNS, RAW_FEATURE_COLUMNS, TARGET_COLUMN

EXPECTED_ROWS = 12330


def test_features_sql_shape_and_columns():
    frame = load_features()
    assert len(frame) == EXPECTED_ROWS, f"expected {EXPECTED_ROWS} rows, got {len(frame)}"
    assert list(frame.columns) == ALL_COLUMNS, f"unexpected columns: {list(frame.columns)}"


def test_features_sql_no_nulls_in_features():
    frame = load_features()
    null_counts = frame[RAW_FEATURE_COLUMNS].isna().sum()
    offenders = {col: int(n) for col, n in null_counts.items() if n > 0}
    assert not offenders, f"feature columns contain nulls: {offenders}"


def main():
    frame = load_features()
    test_features_sql_shape_and_columns()
    test_features_sql_no_nulls_in_features()
    positive_rate = frame[TARGET_COLUMN].mean()
    print(
        f"PASS: features.sql -> {len(frame)} rows x {frame.shape[1]} columns, "
        f"no nulls in features, {positive_rate:.1%} positive."
    )


if __name__ == "__main__":
    main()
