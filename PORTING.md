# Porting: Local to Cloudera AI

The application is built as a shared core behind thin, swappable edges. Porting changes
only the edges. This document lists each swap and the exact change.

| Layer | Local | Cloudera AI | What changes |
|---|---|---|---|
| Data store | Plain Parquet on disk | Iceberg table | Create the Iceberg table with the same schema, load the data |
| Query engine | DuckDB | Impala | Run `sql/features.sql` on Impala; mind the dialect notes below |
| Data access | `src/core/db.py` (DuckDB) | `src/core/db.py` (impyla) | Replace the connection only |
| Model artifacts | `models/*.json`, `*.joblib` | same files in CML | Load in CML; pin runtime library versions |
| Serving | FastAPI over `core.predict` | CML model endpoint or CAI Inference | Wrap the same `core.predict` |
| Narrative (optional) | Hosted chat endpoint via `LLM_*` env | Cloudera AI Inference | Change `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` only |
| Frontend | React dev server | CML Application | Set the API base URL, add auth, deploy the static build |

The shared core that does **not** change: `src/core/schema.py`, `src/core/features.py`,
`src/core/nba.py`, `src/core/predict.py`, and `sql/features.sql`.

---

## 1. Parquet/DuckDB to Iceberg/Impala

Create the Iceberg table with the same schema the local Parquet uses (see the dtypes in
`models/feature_schema.json` and `src/core/schema.py`):

```sql
CREATE TABLE sessions (
  Administrative          INT,
  Administrative_Duration DOUBLE,
  Informational           INT,
  Informational_Duration  DOUBLE,
  ProductRelated          INT,
  ProductRelated_Duration DOUBLE,
  BounceRates             DOUBLE,
  ExitRates               DOUBLE,
  PageValues              DOUBLE,
  SpecialDay              DOUBLE,
  Month                   STRING,
  OperatingSystems        INT,
  Browser                 INT,
  Region                  INT,
  TrafficType             INT,
  VisitorType             STRING,
  Weekend                 BOOLEAN,
  Revenue                 BOOLEAN
)
STORED AS ICEBERG;   -- exact clause depends on the CDP/Impala version
```

Load the same rows (e.g. `LOAD DATA`, `INSERT ... SELECT` from a staged Parquet, or a CTAS
from an external table). Then run `sql/features.sql` on Impala.

**Dialect notes** (the SQL is ANSI-plain and was kept free of DuckDB-only syntax: no
`SELECT * EXCLUDE`, no `QUALIFY`, no list types, no window functions):

- `COALESCE`, `CAST`, `BIGINT`, `DOUBLE`, and `BOOLEAN` are supported identically on both
  engines, so the query body should run unchanged.
- **Identifier case**: Impala folds unquoted identifiers to lower case, so result columns
  may come back as `administrative`, `pagevalues`, etc. The shared `features.py` expects
  the canonical mixed-case names. Reconcile this at the data-access edge (next section),
  not by editing the SQL or the core.

## 2. DuckDB connection to Impala connection (impyla)

Only `src/core/db.py` changes. Keep `load_features()` and its callers as is; replace the
connection and add a one-step column normalization for the identifier-case difference.

```python
# src/core/db.py  (Cloudera variant)
import pandas as pd
from impala.dbapi import connect
from src.config import IMPALA_HOST, IMPALA_PORT, IMPALA_DATABASE
from src.core.schema import ALL_COLUMNS

def _connect():
    # Swap auth to match the cluster (Kerberos/GSSAPI, LDAP, or a CDP token).
    return connect(
        host=IMPALA_HOST, port=IMPALA_PORT, database=IMPALA_DATABASE,
        use_ssl=True, auth_mechanism="GSSAPI",
    )

def _normalize_columns(frame):
    lookup = {c.lower(): c for c in ALL_COLUMNS}
    return frame.rename(columns={c: lookup.get(c.lower(), c) for c in frame.columns})

def load_features():
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(read_features_sql())
        cols = [d[0] for d in cur.description]
        frame = pd.DataFrame(cur.fetchall(), columns=cols)
        return _normalize_columns(frame)
    finally:
        conn.close()
```

Add `IMPALA_HOST`, `IMPALA_PORT`, and `IMPALA_DATABASE` to `src/config.py` (read from the
environment, same pattern as the existing settings). Training reads the whole feature
table this way; serving never touches the warehouse, since a single payload is scored
through `predict()`.

## 3. Model artifacts

The artifacts are already portable: XGBoost native format plus a joblib preprocessing
pipeline plus a JSON schema.

- Copy `models/model.json`, `models/pipeline.joblib`, and `models/feature_schema.json`
  into the CML project (or retrain in CML with `src/train/train.py`).
- **Pin runtime versions to match training.** Use the same `requirements.txt` versions in
  the CML runtime; a mismatched scikit-learn or XGBoost can change `pipeline.joblib`
  loading or scoring. The versions are listed in `requirements.txt`.

## 4. serve/app.py to a model endpoint

Pick the simplest path that fits the deployment.

**Option A: CML model (wrap `core.predict` directly).** Point the CML model at a function
that calls the unchanged core:

```python
# cdsw_predict.py  (deployed as the CML model function)
from src.core.predict import predict

def serve(args):
    # CML passes the request JSON as `args`; return value is serialized to JSON.
    return predict(args)
```

The request/response envelope is the same one the local API uses:

```json
// request: the raw session features object
// response:
{ "intent_score": 0.79, "next_best_action": { "action": "checkout_nudge", "message": "..." } }
```

Confirm the current CML model request/response envelope (some versions wrap the payload,
e.g. `{"request": {...}}`); if so, unwrap in the thin `serve` function only.

**Option B: CAI Inference Service.** Containerize the FastAPI app (`src/serve/app.py`) as
is and deploy it as an inference service. The core is unchanged; only the ingress and
auth differ.

## 5. Narrative endpoint to Cloudera AI Inference

The optional narrative layer (`src/core/llm.py` + `src/core/narrate.py`, exposed as
`POST /narrate`) calls a chat-completions-style HTTP endpoint. Cloudera AI Inference
exposes the same API shape, so the client ports unchanged; only the environment moves:

- `LLM_BASE_URL`: the Cloudera AI Inference endpoint base for the deployed model
  (the path that serves `/chat/completions`).
- `LLM_API_KEY`: the CDP workload/JWT token used to authenticate to the endpoint.
- `LLM_MODEL`: the deployed model's name as registered in the inference service.

Scoring never depends on this layer: with the variables unset, `/narrate` reports
`enabled=false` and the frontend hides the narrative card, so the model endpoint can be
ported first and the narrative wired up later.

## 6. React frontend to a CML Application

- Set `VITE_API_BASE_URL` to the CAI/CML endpoint URL (it is already read from the
  environment, never hardcoded).
- Add the auth token to requests in `frontend/src/api.js` (e.g. an `Authorization` header
  with a CDP token), to match how the endpoint authenticates.
- Handle CORS: add the Application's origin to the endpoint's allowed origins (locally
  this is `CORS_ORIGINS`).
- Build the static bundle with `npm run build` and deploy `frontend/dist/` as a CML
  Application.
