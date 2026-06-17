"""Parity test: the shared feature prep produces identical vectors for batch,
single-row, and serve-payload code paths. This is the guard that keeps train and
serve in lockstep (no skew).

Run as a standalone script (python tests/test_feature_parity.py) or via pytest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from pandas.testing import assert_frame_equal

from src.config import SAMPLE_SESSIONS_PATH
from src.core.db import load_features
from src.core.features import prepare, prepare_payload
from src.core.schema import RAW_FEATURE_COLUMNS, to_native

import json

# How many rows to check row-by-row. Enough to cover varied sessions, small enough to
# stay fast.
SAMPLE_ROWS = 200


def _feature_sample() -> pd.DataFrame:
    return load_features().head(SAMPLE_ROWS).reset_index(drop=True)


def test_batch_matches_single_row():
    """prepare(batch) equals prepare() applied to each row individually."""
    frame = _feature_sample()
    batch = prepare(frame).reset_index(drop=True)
    for position in range(len(frame)):
        single = prepare(frame.iloc[[position]]).reset_index(drop=True)
        expected = batch.iloc[[position]].reset_index(drop=True)
        assert_frame_equal(single, expected, obj=f"row {position}")


def test_serve_payload_matches_training_path():
    """A session scored through the JSON-payload serve path equals the batch path.

    Each raw row is round-tripped to a JSON-native payload dict, validated, and prepared
    via prepare_payload, then compared to the same row prepared through the batch path.
    """
    frame = _feature_sample()
    batch = prepare(frame).reset_index(drop=True)
    for position in range(len(frame)):
        row = frame.iloc[position]
        payload = {col: to_native(col, row[col]) for col in RAW_FEATURE_COLUMNS}
        served = prepare_payload(payload).reset_index(drop=True)
        expected = batch.iloc[[position]].reset_index(drop=True)
        assert_frame_equal(served, expected, obj=f"payload row {position}")


def test_demo_sessions_prepare():
    """Every shipped demo session validates and prepares to a single feature row."""
    samples = json.loads(Path(SAMPLE_SESSIONS_PATH).read_text())
    for sample in samples:
        prepared = prepare_payload(sample["features"])
        assert len(prepared) == 1, f"{sample['session_id']} did not prepare to one row"


def main():
    test_batch_matches_single_row()
    test_serve_payload_matches_training_path()
    test_demo_sessions_prepare()
    print(
        f"PASS: batch / single-row / serve-payload parity holds over {SAMPLE_ROWS} rows "
        "and all demo sessions."
    )


if __name__ == "__main__":
    main()
