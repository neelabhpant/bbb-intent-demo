"""Smoke test for the shared predict() function over the demo sessions.

Run as a standalone script (python tests/test_predict.py) or via pytest. Requires the
model artifacts; run src/train/train.py first.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SAMPLE_SESSIONS_PATH
from src.core.predict import predict

VALID_ACTIONS = {
    "checkout_nudge",
    "bundle_offer",
    "capture_email_discount",
    "re_engage_popular",
    "loyalty_reminder",
}


def _samples():
    return json.loads(Path(SAMPLE_SESSIONS_PATH).read_text())


def test_envelope_shape():
    for sample in _samples():
        result = predict(sample["features"])
        assert set(result.keys()) == {"intent_score", "next_best_action", "drivers"}
        assert 0.0 <= result["intent_score"] <= 1.0
        nba = result["next_best_action"]
        assert set(nba.keys()) == {"action", "message"}
        assert nba["action"] in VALID_ACTIONS
        assert isinstance(nba["message"], str) and nba["message"]


def test_drivers_shape():
    for sample in _samples():
        drivers = predict(sample["features"])["drivers"]
        assert drivers, f"no drivers for {sample['session_id']}"
        for driver in drivers:
            assert set(driver.keys()) == {"feature", "value", "contribution", "direction"}
            assert driver["direction"] in {"up", "down"}
        magnitudes = [abs(d["contribution"]) for d in drivers]
        assert magnitudes == sorted(magnitudes, reverse=True), "drivers not sorted by magnitude"


def test_deterministic():
    for sample in _samples():
        first = predict(sample["features"])
        second = predict(sample["features"])
        assert first == second, f"non-deterministic output for {sample['session_id']}"


def main():
    test_envelope_shape()
    test_drivers_shape()
    test_deterministic()
    print("PASS: predict() returns a valid, deterministic envelope (with drivers) for all demo sessions.")


if __name__ == "__main__":
    main()
