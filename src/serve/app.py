"""FastAPI app exposing the shared predict() as POST /predict.

A thin local stand-in for the Cloudera model endpoint: the request body is a raw session
features object and the response is the predict() envelope. Validation stays in the core
(schema.py), so a bad payload surfaces as HTTP 400 with a clear message. CORS is enabled
for the React dev origins from config. When porting, the CML model deployment wraps the
same core.predict function; only this thin edge changes.
"""
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import CORS_ORIGINS
from src.core.narrate import narrate
from src.core.predict import predict
from src.core.schema import PayloadValidationError

app = FastAPI(title="Purchase Intent Scoring", version="1.0.0")

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Documentation example: a raw session. PageValues is still part of the raw contract;
# the shipped model simply ignores it.
EXAMPLE_SESSION = {
    "Administrative": 3,
    "Administrative_Duration": 37.5,
    "Informational": 0,
    "Informational_Duration": 0.0,
    "ProductRelated": 18,
    "ProductRelated_Duration": 607.5,
    "BounceRates": 0.0,
    "ExitRates": 0.0105,
    "PageValues": 0.0,
    "SpecialDay": 0.0,
    "Month": "Nov",
    "OperatingSystems": 2,
    "Browser": 2,
    "Region": 3,
    "TrafficType": 2,
    "VisitorType": "Returning_Visitor",
    "Weekend": False,
}


class NextBestAction(BaseModel):
    action: str
    message: str


class Driver(BaseModel):
    feature: str
    value: bool | int | float | str
    contribution: float
    direction: str


class PredictResponse(BaseModel):
    intent_score: float
    next_best_action: NextBestAction
    drivers: list[Driver]


class NarrateResponse(BaseModel):
    enabled: bool
    narrative: str | None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(payload: dict = Body(..., examples=[EXAMPLE_SESSION])):
    """Score a raw session and return its intent score and next-best-action."""
    try:
        return predict(payload)
    except PayloadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/narrate", response_model=NarrateResponse)
def narrate_endpoint(payload: dict = Body(..., examples=[EXAMPLE_SESSION])):
    """Generate a short plain-language narrative for a raw session.

    Scoring never depends on this endpoint: with no model endpoint configured it
    returns enabled=false and the UI hides the narrative card. Defined as a plain
    function so the blocking HTTP call runs on the framework's worker threads.
    """
    try:
        return narrate(payload)
    except PayloadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
