"""Deterministic next-best-action rules.

Pure, explainable rules mapping an intent score plus a few session signals to a single
recommended action. No model state and no randomness: identical inputs always yield the
same action, so the front end stays dumb and the rules port unchanged. Thresholds come
from config so they can be tuned without touching this logic.
"""
from src.config import (
    DISENGAGE_RATE_THRESHOLD,
    INTENT_HIGH_THRESHOLD,
    INTENT_MEDIUM_THRESHOLD,
)


def intent_tier(score: float) -> str:
    """Map a score to the wording tier used across the demo: high, medium, or low."""
    if score >= INTENT_HIGH_THRESHOLD:
        return "high"
    if score >= INTENT_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def next_best_action(score: float, features: dict) -> dict:
    """Return {action, message} for an intent score and the session's raw features.

    Signal-based overrides take precedence over the score tier, so a disengaging or a
    loyal-but-undecided session gets a targeted action instead of a generic one.
    """
    exit_rate = float(features.get("ExitRates", 0.0) or 0.0)
    bounce_rate = float(features.get("BounceRates", 0.0) or 0.0)
    visitor_type = str(features.get("VisitorType", ""))
    is_high_intent = score >= INTENT_HIGH_THRESHOLD

    # Override: a disengaging session (high exit/bounce) that is not already high intent.
    if not is_high_intent and (
        exit_rate >= DISENGAGE_RATE_THRESHOLD or bounce_rate >= DISENGAGE_RATE_THRESHOLD
    ):
        return {
            "action": "re_engage_popular",
            "message": "Show popular categories and top-rated products to re-engage.",
        }

    # Override: a returning visitor who has not reached high intent yet.
    if not is_high_intent and visitor_type == "Returning_Visitor":
        return {
            "action": "loyalty_reminder",
            "message": "Surface a saved-cart and loyalty reminder to bring them back.",
        }

    # Score tiers.
    if is_high_intent:
        return {
            "action": "checkout_nudge",
            "message": "Offer a free-shipping threshold and streamlined checkout to close.",
        }
    if score >= INTENT_MEDIUM_THRESHOLD:
        return {
            "action": "bundle_offer",
            "message": "Surface complementary and bundled items to grow the basket.",
        }
    return {
        "action": "capture_email_discount",
        "message": "Offer a first-purchase discount to capture the email.",
    }
