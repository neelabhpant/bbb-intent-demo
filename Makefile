# Local orchestration. The virtualenv lives outside the repo by default so it is not
# synced by cloud storage; override VENV to place it elsewhere.
VENV ?= $(HOME)/.venvs/bbb-intent-demo
PY = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn
API_PORT ?= 8000
WEB_PORT ?= 5173

.PHONY: help setup data train test api web demo clean kill

# Kill only LISTENING servers on a port (never client connections such as the browser).
define free_port
lsof -ti tcp:$(1) -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
endef

help:
	@echo "Targets:"
	@echo "  setup  Create the venv, install Python and frontend deps, copy env files"
	@echo "  data   Download the dataset and build the local Parquet + sample sessions"
	@echo "  train  Train the model and save artifacts"
	@echo "  test   Run the SQL, feature-parity, and predict checks"
	@echo "  api    Serve the FastAPI scoring endpoint (port $(API_PORT))"
	@echo "  web    Run the React dev server (port $(WEB_PORT))"
	@echo "  demo   One command: setup + data + train, then run API and web together"
	@echo "  kill   Stop any servers left running on the API and web ports"
	@echo "  clean  Remove derived data and model artifacts"

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	cp -n config/.env.example config/.env || true
	cd frontend && npm install && (cp -n .env.example .env || true)

data:
	$(PY) data/download_data.py
	$(PY) data/build_table.py

train:
	$(PY) src/train/train.py

test:
	$(PY) tests/validate_features_sql.py
	$(PY) tests/test_feature_parity.py
	$(PY) tests/test_predict.py
	$(PY) tests/test_narrate.py

api:
	@$(call free_port,$(API_PORT))
	$(UVICORN) src.serve.app:app --port $(API_PORT) --reload

web:
	cd frontend && npm run dev -- --port $(WEB_PORT)

kill:
	@$(call free_port,$(API_PORT))
	@$(call free_port,$(WEB_PORT))
	@echo "Stopped any servers on ports $(API_PORT) and $(WEB_PORT)."

demo: setup data train
	@echo "API on http://localhost:$(API_PORT) , web on http://localhost:$(WEB_PORT)"
	@bash -c 'set -e; \
	  $(call free_port,$(API_PORT)); \
	  $(call free_port,$(WEB_PORT)); \
	  $(UVICORN) src.serve.app:app --port $(API_PORT) & API_PID=$$!; \
	  trap "kill $$API_PID 2>/dev/null || true; $(call free_port,$(API_PORT))" EXIT INT TERM; \
	  sleep 2; \
	  cd frontend && npm run dev -- --port $(WEB_PORT)'

clean:
	rm -rf data/raw data/parquet data/sample_sessions.json models/*.json models/*.joblib
