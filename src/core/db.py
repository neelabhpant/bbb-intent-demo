"""Single database access module.

Locally this opens a DuckDB connection and exposes the Parquet file as the `sessions`
table. When porting to Cloudera, replace `_connect` with an impyla connection to Impala
where `sessions` is the Iceberg table; the portable SQL in sql/features.sql and every
caller stay unchanged. Swapping engines is a connection change, not a logic change.
"""
import duckdb
import pandas as pd

from src.config import PARQUET_PATH, SQL_DIR

FEATURES_SQL_PATH = SQL_DIR / "features.sql"


def read_features_sql() -> str:
    """Return the portable feature query text."""
    return FEATURES_SQL_PATH.read_text()


def _connect():
    """Open the local DuckDB connection with the `sessions` view over the Parquet.

    This connection is the only local-specific edge. Swap it for an impyla Impala
    connection when porting; nothing else in the module or its callers changes.
    """
    connection = duckdb.connect()
    connection.read_parquet(str(PARQUET_PATH)).create_view("sessions")
    return connection


def load_features() -> pd.DataFrame:
    """Run sql/features.sql against the data warehouse and return the result."""
    connection = _connect()
    try:
        return connection.execute(read_features_sql()).fetchdf()
    finally:
        connection.close()


if __name__ == "__main__":
    frame = load_features()
    print(f"Loaded {len(frame)} rows x {frame.shape[1]} columns from sql/features.sql")
    print(frame.dtypes)
