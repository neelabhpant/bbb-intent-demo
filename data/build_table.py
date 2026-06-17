"""Build the local Parquet table and a small set of demo sessions from the raw CSV.

The local data layer is plain Parquet on disk (no local Iceberg/PyIceberg catalog);
the same schema is recreated as an Iceberg table during porting. sample_sessions.json
holds a handful of varied sessions for the demo, each as the raw input the API scores
plus the ground-truth label kept aside for the narrative (never sent to the model).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.config import PARQUET_PATH, RAW_CSV_NAME, RAW_DATA_DIR, SAMPLE_SESSIONS_PATH
from src.core.schema import (
    ALL_COLUMNS,
    RAW_FEATURE_COLUMNS,
    TARGET_COLUMN,
    coerce_dtypes,
    to_native,
)


def _load_raw() -> pd.DataFrame:
    csv_path = RAW_DATA_DIR / RAW_CSV_NAME
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Raw CSV not found at {csv_path}. Run data/download_data.py first."
        )
    frame = pd.read_csv(csv_path)
    return coerce_dtypes(frame[ALL_COLUMNS])


def _write_parquet(frame: pd.DataFrame) -> None:
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(PARQUET_PATH, engine="pyarrow", index=False)
    print(f"Wrote {len(frame)} rows -> {PARQUET_PATH}")


def _select_samples(frame: pd.DataFrame):
    """Pick a deterministic, varied set of sessions for the demo picker."""
    buyers = frame[frame[TARGET_COLUMN]]
    non_buyers = frame[~frame[TARGET_COLUMN]]

    picks = []  # (label, index)
    for idx in buyers.sort_values("PageValues", ascending=False).head(3).index:
        picks.append(("High-intent buyer: strong page value", idx))
    for idx in non_buyers.sort_values("ProductRelated", ascending=False).head(2).index:
        picks.append(("Engaged browser, did not purchase", idx))
    zero_value = non_buyers[non_buyers["PageValues"] == 0]
    for idx in zero_value.sort_values("ExitRates", ascending=False).head(2).index:
        picks.append(("High exit rate, low intent", idx))
    new_visitors = non_buyers[non_buyers["VisitorType"] == "New_Visitor"]
    if len(new_visitors):
        idx = new_visitors.sort_values("ProductRelated", ascending=False).index[0]
        picks.append(("New visitor, exploratory session", idx))

    seen = set()
    ordered = []
    for label, idx in picks:
        if idx not in seen:
            seen.add(idx)
            ordered.append((label, idx))
    return ordered


def _build_samples(frame: pd.DataFrame) -> list:
    samples = []
    for position, (label, idx) in enumerate(_select_samples(frame), start=1):
        row = frame.loc[idx]
        features = {col: to_native(col, row[col]) for col in RAW_FEATURE_COLUMNS}
        samples.append(
            {
                "session_id": f"sess_{position:02d}",
                "label": label,
                "actual_revenue": bool(row[TARGET_COLUMN]),
                "features": features,
            }
        )
    return samples


def main() -> None:
    frame = _load_raw()
    _write_parquet(frame)

    positive_rate = frame[TARGET_COLUMN].mean()
    print(f"Class balance: {positive_rate:.1%} positive (Revenue=True).")

    samples = _build_samples(frame)
    SAMPLE_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_SESSIONS_PATH.write_text(json.dumps(samples, indent=2) + "\n")
    print(f"Wrote {len(samples)} demo sessions -> {SAMPLE_SESSIONS_PATH}")


if __name__ == "__main__":
    main()
