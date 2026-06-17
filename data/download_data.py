"""Download and verify the public UCI Online Shoppers Purchasing Intention Dataset.

Dataset: Sakar, C. & Kastro, Y. (2018). Online Shoppers Purchasing Intention Dataset.
UCI Machine Learning Repository. https://doi.org/10.24432/C5F88Q
License: Creative Commons Attribution 4.0 International (CC BY 4.0).
"""
import argparse
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests

from src.config import DATASET_URL, RAW_CSV_NAME, RAW_DATA_DIR
from src.core.schema import ALL_COLUMNS

EXPECTED_ROWS = 12330


def _download_csv(csv_path: Path) -> str:
    """Fetch the dataset archive and extract its CSV member to csv_path."""
    print(f"Downloading dataset from {DATASET_URL}")
    response = requests.get(DATASET_URL, timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        csv_members = [m for m in archive.namelist() if m.lower().endswith(".csv")]
        if not csv_members:
            raise RuntimeError(f"No CSV found in archive members: {archive.namelist()}")
        member = csv_members[0]
        with archive.open(member) as source:
            csv_path.write_bytes(source.read())
    return member


def _verify(csv_path: Path) -> None:
    """Confirm the expected columns and row count are present."""
    frame = pd.read_csv(csv_path)
    missing = [col for col in ALL_COLUMNS if col not in frame.columns]
    if missing:
        raise RuntimeError(f"Dataset is missing expected columns: {missing}")
    rows, cols = frame.shape
    print(f"Verified {rows} rows x {cols} columns.")
    if rows != EXPECTED_ROWS:
        print(f"Warning: expected {EXPECTED_ROWS} rows but found {rows}.")


def _print_license() -> None:
    print(
        "\nDataset license: CC BY 4.0 (attribution required).\n"
        "Cite: Sakar, C. & Kastro, Y. (2018). Online Shoppers Purchasing Intention "
        "Dataset.\nUCI Machine Learning Repository. https://doi.org/10.24432/C5F88Q"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the raw sessions dataset.")
    parser.add_argument(
        "--force", action="store_true", help="Re-download even if the CSV is present."
    )
    args = parser.parse_args()

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DATA_DIR / RAW_CSV_NAME

    if csv_path.exists() and not args.force:
        print(f"Raw CSV already present at {csv_path} (use --force to re-download).")
    else:
        member = _download_csv(csv_path)
        print(f"Extracted {member} -> {csv_path}")

    _verify(csv_path)
    _print_license()


if __name__ == "__main__":
    main()
