"""Raw session schema: the input column contract shared by data prep, training, and
serving. This is the dataset's raw shape, distinct from the engineered feature vector
the trained model consumes (that ordered list is saved as models/feature_schema.json
at train time).
"""

TARGET_COLUMN = "Revenue"

# The 17 raw features in canonical order.
RAW_FEATURE_COLUMNS = [
    "Administrative",
    "Administrative_Duration",
    "Informational",
    "Informational_Duration",
    "ProductRelated",
    "ProductRelated_Duration",
    "BounceRates",
    "ExitRates",
    "PageValues",
    "SpecialDay",
    "Month",
    "OperatingSystems",
    "Browser",
    "Region",
    "TrafficType",
    "VisitorType",
    "Weekend",
]

INT_COLUMNS = [
    "Administrative",
    "Informational",
    "ProductRelated",
    "OperatingSystems",
    "Browser",
    "Region",
    "TrafficType",
]
FLOAT_COLUMNS = [
    "Administrative_Duration",
    "Informational_Duration",
    "ProductRelated_Duration",
    "BounceRates",
    "ExitRates",
    "PageValues",
    "SpecialDay",
]
CATEGORICAL_COLUMNS = ["Month", "VisitorType"]
BOOL_COLUMNS = ["Weekend"]

ALL_COLUMNS = RAW_FEATURE_COLUMNS + [TARGET_COLUMN]


def coerce_dtypes(frame):
    """Coerce a raw sessions DataFrame to canonical, port-stable dtypes.

    Produces clean int64 / float64 / string / boolean columns so the local Parquet
    schema maps directly onto the Iceberg/Impala table created during porting.
    """
    out = frame.copy()
    for col in INT_COLUMNS:
        out[col] = out[col].astype("int64")
    for col in FLOAT_COLUMNS:
        out[col] = out[col].astype("float64")
    for col in CATEGORICAL_COLUMNS:
        out[col] = out[col].astype("string")
    for col in BOOL_COLUMNS:
        out[col] = out[col].astype("bool")
    if TARGET_COLUMN in out.columns:
        out[TARGET_COLUMN] = out[TARGET_COLUMN].astype("bool")
    return out


def to_native(column, value):
    """Convert a single cell to a JSON-native scalar based on its schema dtype."""
    if column in INT_COLUMNS:
        return int(value)
    if column in FLOAT_COLUMNS:
        return float(value)
    if column in BOOL_COLUMNS:
        return bool(value)
    return str(value)


# Known categorical values, for reference and documentation. Unseen values are not
# rejected at validation time: the fitted encoder handles them (handle_unknown).
KNOWN_MONTHS = ["Feb", "Mar", "May", "June", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KNOWN_VISITOR_TYPES = ["Returning_Visitor", "New_Visitor", "Other"]


class PayloadValidationError(ValueError):
    """Raised when an incoming session payload does not match the raw schema."""


def _coerce_scalar(column, value):
    """Validate and coerce one payload value to its schema dtype, or raise."""
    if value is None:
        raise PayloadValidationError(f"Feature '{column}' is required and cannot be null.")

    if column in INT_COLUMNS:
        if isinstance(value, bool):
            raise PayloadValidationError(f"Feature '{column}' must be an integer, got boolean.")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            raise PayloadValidationError(f"Feature '{column}' must be a whole number, got {value!r}.")
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as exc:
                raise PayloadValidationError(f"Feature '{column}' must be an integer, got {value!r}.") from exc
        raise PayloadValidationError(f"Feature '{column}' must be an integer, got {type(value).__name__}.")

    if column in FLOAT_COLUMNS:
        if isinstance(value, bool):
            raise PayloadValidationError(f"Feature '{column}' must be numeric, got boolean.")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError as exc:
                raise PayloadValidationError(f"Feature '{column}' must be numeric, got {value!r}.") from exc
        raise PayloadValidationError(f"Feature '{column}' must be numeric, got {type(value).__name__}.")

    if column in BOOL_COLUMNS:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "0", "1"):
            return value.strip().lower() in ("true", "1")
        raise PayloadValidationError(f"Feature '{column}' must be boolean, got {value!r}.")

    # Categorical columns: non-empty string.
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise PayloadValidationError(f"Feature '{column}' must be a non-empty string, got {value!r}.")


def validate_payload(payload):
    """Validate a raw session payload against the schema and return a coerced dict.

    Checks that every required raw feature is present and coerces each value to its
    schema dtype. Unknown extra keys are ignored. Raises PayloadValidationError on any
    missing field or type mismatch. This is the single entry-point gate used by serve.
    """
    if not isinstance(payload, dict):
        raise PayloadValidationError(f"Payload must be an object, got {type(payload).__name__}.")
    missing = [col for col in RAW_FEATURE_COLUMNS if col not in payload]
    if missing:
        raise PayloadValidationError(f"Payload is missing required features: {missing}")
    return {col: _coerce_scalar(col, payload[col]) for col in RAW_FEATURE_COLUMNS}
