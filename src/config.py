"""Central configuration: repo-relative paths and environment-driven settings.

No machine-specific absolute paths or hostnames are baked into this module. Every
path is derived relative to the repository root, and every value can be overridden
through the environment (optionally via config/.env). Host and origin values such as
the CORS origins are supplied only through the environment so nothing local leaks
into committed code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Load config/.env if present. Real environment variables take precedence.
load_dotenv(REPO_ROOT / "config" / ".env", override=False)


def _path(env_key: str, default_rel: str) -> Path:
    """Return an absolute Path from the environment, or a repo-relative default."""
    value = os.environ.get(env_key)
    return Path(value).expanduser() if value else REPO_ROOT / default_rel


def _csv_env(env_key: str) -> list:
    """Parse a comma-separated environment value into a clean list of strings."""
    return [item.strip() for item in os.environ.get(env_key, "").split(",") if item.strip()]


# --- Paths (all repo-relative by default) ---
DATA_DIR = _path("DATA_DIR", "data")
RAW_DATA_DIR = _path("RAW_DATA_DIR", "data/raw")
PARQUET_PATH = _path("PARQUET_PATH", "data/parquet/sessions.parquet")
SAMPLE_SESSIONS_PATH = _path("SAMPLE_SESSIONS_PATH", "data/sample_sessions.json")
MODELS_DIR = _path("MODELS_DIR", "models")
SQL_DIR = _path("SQL_DIR", "sql")

# --- Dataset source ---
DATASET_URL = os.environ.get(
    "DATASET_URL",
    "https://archive.ics.uci.edu/static/public/468/"
    "online+shoppers+purchasing+intention+dataset.zip",
)
RAW_CSV_NAME = os.environ.get("RAW_CSV_NAME", "online_shoppers_intention.csv")

# --- Reproducibility ---
RANDOM_STATE = int(os.environ.get("RANDOM_STATE", "42"))

# --- Scoring and next-best-action thresholds ---
INTENT_HIGH_THRESHOLD = float(os.environ.get("INTENT_HIGH_THRESHOLD", "0.6"))
INTENT_MEDIUM_THRESHOLD = float(os.environ.get("INTENT_MEDIUM_THRESHOLD", "0.3"))
DISENGAGE_RATE_THRESHOLD = float(os.environ.get("DISENGAGE_RATE_THRESHOLD", "0.05"))

# --- Serving ---
CORS_ORIGINS = _csv_env("CORS_ORIGINS")

# --- Narrative explanations (optional; any chat-completions-style HTTP endpoint) ---
# When LLM_BASE_URL or LLM_MODEL is unset, the narrate endpoint reports enabled=false
# and the UI hides the narrative card. The scoring path never uses these settings.
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "20"))
