"""Plain-language narrative for a scored session.

Turns the predict() output (score, next-best-action, drivers) into a 2-3 sentence
summary for a business reader by calling the configured model endpoint. The prompt pins
every fact: the model is asked to rephrase, never to invent. Scoring itself stays fully
deterministic and LLM-free; this module is an optional layer on top.

Successful narratives are cached per payload, so repeat clicks on the same demo session
are instant and cost nothing. Failures are not cached and retry on the next request.
"""
import json
from functools import lru_cache

from src.config import INTENT_HIGH_THRESHOLD, INTENT_MEDIUM_THRESHOLD
from src.core import llm
from src.core.nba import intent_tier
from src.core.predict import predict

# Friendly wording for feature keys, mirroring the labels the UI shows.
FEATURE_LABELS = {
    "Administrative": "Admin pages viewed",
    "Administrative_Duration": "Time on admin pages",
    "Informational": "Info pages viewed",
    "Informational_Duration": "Time on info pages",
    "ProductRelated": "Product pages viewed",
    "ProductRelated_Duration": "Time on product pages",
    "BounceRates": "Bounce rate",
    "ExitRates": "Exit rate",
    "SpecialDay": "Special-day proximity",
    "Month": "Month",
    "OperatingSystems": "Operating system",
    "Browser": "Browser",
    "Region": "Region",
    "TrafficType": "Traffic type",
    "VisitorType": "Visitor",
    "Weekend": "Weekend visit",
    "total_pages": "Total pages viewed",
    "total_duration": "Total session time",
    "avg_product_duration": "Average time per product page",
}

MONTH_NAMES = {
    "Feb": "February", "Mar": "March", "May": "May", "June": "June", "Jul": "July",
    "Aug": "August", "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December",
}

VISITOR_WORDING = {
    "Returning_Visitor": "returning visitor",
    "New_Visitor": "new visitor",
    "Other": "other visitor type",
}

SYSTEM_PROMPT = (
    "You are a retail analytics assistant writing for a merchandising manager. "
    "Write exactly 2-3 sentences of plain language. No jargon, no markdown, no bullet "
    "points, no headings. Use only the facts provided; never invent numbers, behaviors, "
    "or causes. Always mention the recommended action in plain words."
)


def _format_value(feature: str, value) -> str:
    """Render a driver's session value the way the UI would."""
    if feature == "Month":
        return MONTH_NAMES.get(value, str(value))
    if feature == "VisitorType":
        return VISITOR_WORDING.get(value, str(value))
    if feature == "Weekend":
        return "yes" if value else "no"
    if feature in ("ExitRates", "BounceRates"):
        return f"{float(value) * 100:.1f}%"
    if feature.endswith("_Duration") or feature in ("total_duration", "avg_product_duration"):
        return f"{round(float(value))}s"
    return str(value)


def build_messages(prediction: dict, features: dict) -> list:
    """Build the chat messages from a predict() result. Pure and deterministic."""
    score = prediction["intent_score"]
    tier = intent_tier(score)
    action = prediction["next_best_action"]

    driver_lines = []
    for driver in prediction["drivers"]:
        label = FEATURE_LABELS.get(driver["feature"], driver["feature"])
        value = _format_value(driver["feature"], driver["value"])
        push = "pushes the score up" if driver["direction"] == "up" else "pushes the score down"
        driver_lines.append(f"  * {label} = {value} ({push})")

    facts = (
        "Summarize this shopping session's purchase-intent score for a business reader.\n\n"
        "Facts:\n"
        f"- Purchase-intent score: {round(score * 100)}% ({tier} intent; tiers: "
        f"high >= {round(INTENT_HIGH_THRESHOLD * 100)}%, "
        f"medium >= {round(INTENT_MEDIUM_THRESHOLD * 100)}%, low below that)\n"
        f"- Recommended action: {action['message']} ({action['action']})\n"
        "- Top signals driving the score (strongest first):\n"
        + "\n".join(driver_lines)
        + "\n\nWrite 2-3 sentences: what the score means, the one or two signals that "
        "matter most, and the recommended action."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": facts},
    ]


@lru_cache(maxsize=128)
def _generate(payload_key: str) -> str:
    """Score the payload and generate its narrative. Raises LLMError on failure, so
    failures are never cached and the next request retries."""
    payload = json.loads(payload_key)
    prediction = predict(payload)
    return llm.chat(build_messages(prediction, payload))


def narrate(payload: dict) -> dict:
    """Return {enabled, narrative} for a raw session payload.

    enabled=False means no model endpoint is configured (the UI hides the card).
    enabled=True with narrative=None means the endpoint failed this time.
    Payload validation errors propagate, matching the scoring endpoint's behavior.
    """
    if not llm.is_configured():
        return {"enabled": False, "narrative": None}
    key = json.dumps(payload, sort_keys=True, default=str)
    try:
        return {"enabled": True, "narrative": _generate(key)}
    except llm.LLMError:
        return {"enabled": True, "narrative": None}
