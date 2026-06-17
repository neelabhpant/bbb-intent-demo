# Architecture

End-to-end view of the purchase-intent demo. The guiding principle is **shared core,
swappable edges**: all platform-specific concerns live behind thin edges (data
connection, serving wrapper, LLM client, frontend config). Porting to Cloudera AI swaps
the edges; it never rewrites the logic. See [PORTING.md](PORTING.md) for the exact swaps.

**Legend** — in the diagram below: dark-blue = shared core (identical local and ported),
amber = swappable edge, teal cylinders = data/artifact stores, purple = external service.

## End-to-end system

```mermaid
flowchart TB
  classDef store fill:#16263f,stroke:#5bbf9f,color:#e8f3ee;
  classDef edge fill:#3a2a12,stroke:#e8a33d,color:#f6e6cf;
  classDef core fill:#13233a,stroke:#46b3a3,color:#dcefef;
  classDef ext fill:#2a1530,stroke:#c56,color:#f6dde6;

  subgraph OFFLINE["Offline — build &amp; train (batch)"]
    direction TB
    DL["download_data.py<br/>fetch UCI · verify license"]
    BUILD["build_table.py<br/>write Parquet · sample sessions"]
    PARQ[("sessions.parquet<br/>local data store")]
    SQL["sql/features.sql<br/>portable ANSI projection"]
    DBE["core/db.py<br/>DuckDB connection"]
    FP["core/features.py<br/>prepare() — shared prep"]
    TR["train/train.py<br/>split · scale_pos_weight<br/>AUC-ROC / PR-AUC · drop PageValues"]
    ART[("models/<br/>model.json · pipeline.joblib<br/>feature_schema.json")]
    DL --> BUILD --> PARQ --> DBE --> SQL --> FP --> TR --> ART
  end

  subgraph ONLINE["Online — serve (per request)"]
    direction TB
    UI["Frontend — React / Vite<br/>SessionPicker · IntentGauge · ActionCard<br/>DriverBars · NarrativeCard"]
    API["serve/app.py — FastAPI<br/>GET /health · POST /predict · POST /narrate"]

    subgraph COREG["Shared core — identical local &amp; Cloudera"]
      direction TB
      VAL["schema.validate_payload()"]
      PRP["features.prepare()"]
      PIPE["pipeline.transform<br/>ColumnTransformer"]
      XGB["XGBoost predict_proba<br/>+ SHAP drivers"]
      NBA["nba.next_best_action()<br/>deterministic rules"]
      VAL --> PRP --> PIPE --> XGB --> NBA
    end

    NAR["core/narrate.py<br/>grounded prompt"]
    LLMC["core/llm.py<br/>chat client"]
    LLM(["LLM endpoint<br/>local model / Cloudera AI Inference"])

    UI -->|"POST /predict"| API
    API --> VAL
    NBA -->|"score · action · drivers"| API
    API -->|"JSON"| UI
    UI -->|"POST /narrate"| NAR
    NAR --> LLMC --> LLM
    LLM -->|"2-3 sentence summary"| UI
  end

  ART -. "loaded once, cached" .-> PIPE
  ART -.-> XGB
  ART -.-> VAL

  class PARQ,ART store;
  class DBE,API,LLMC edge;
  class VAL,PRP,PIPE,XGB,NBA,FP,NAR core;
  class LLM ext;
```

### Offline lifecycle (build once)
1. `data/download_data.py` fetches the public UCI dataset and verifies the license.
2. `data/build_table.py` writes `data/parquet/sessions.parquet` and a handful of demo
   sessions.
3. `sql/features.sql` (run through `core/db.py`, DuckDB locally) projects the portable
   feature source; `core/features.py` derives the shared feature vector.
4. `src/train/train.py` trains the XGBoost pipeline (drops `PageValues` to avoid leakage,
   handles class imbalance, reports AUC-ROC / PR-AUC) and writes three portable artifacts
   to `models/`.

### Online lifecycle (per request)
1. The React UI POSTs a raw session to `/predict`.
2. The shared core validates the payload against the schema, prepares features, transforms
   them with the fitted pipeline, scores with the booster, computes SHAP **drivers**, and
   attaches the deterministic **next-best-action** — returned together as one JSON object.
3. Separately, the UI POSTs to `/narrate`; `core/narrate.py` builds a prompt strictly from
   the model's own score, drivers, and action, and `core/llm.py` calls the LLM endpoint for
   a short plain-language summary. This layer is optional: if no endpoint is configured,
   `/narrate` reports `enabled: false` and the UI hides the card — scoring is unaffected.

## Shared core, swappable edges (local → Cloudera)

```mermaid
flowchart LR
  classDef local fill:#13233a,stroke:#46b3a3,color:#dcefef;
  classDef cdp fill:#3a2a12,stroke:#e8a33d,color:#f6e6cf;

  subgraph L["Local — one command"]
    direction TB
    L1["Plain Parquet on disk"]
    L2["DuckDB · core/db.py"]
    L3["FastAPI over core.predict"]
    L4["Chat endpoint via LLM_* env"]
    L5["React dev server"]
  end

  subgraph C["Cloudera AI — port swaps edges only"]
    direction TB
    C1["Iceberg table"]
    C2["Impala · core/db.py"]
    C3["CML model / CAI Inference"]
    C4["Cloudera AI Inference"]
    C5["CML Application"]
  end

  L1 ==>|"same schema"| C1
  L2 ==>|"connection only"| C2
  L3 ==>|"same predict()"| C3
  L4 ==>|"env only"| C4
  L5 ==>|"static build"| C5

  class L1,L2,L3,L4,L5 local;
  class C1,C2,C3,C4,C5 cdp;
```

**Shared core (unchanged when porting):** `src/core/schema.py`, `src/core/features.py`,
`src/core/predict.py`, `src/core/nba.py`, `src/core/narrate.py`, `src/core/llm.py`, and
`sql/features.sql`.

**Edges (the only things that change):** the data connection (`src/core/db.py`), the
serving wrapper (`src/serve/app.py`), the LLM endpoint configuration (`LLM_*` env), and the
frontend's `VITE_API_BASE_URL`.
