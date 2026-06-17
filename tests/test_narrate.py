"""Tests for the narrative layer: prompt building, the enabled/disabled envelope, and
caching. No live model endpoint is needed; the transport seam is stubbed in-process.

Run as a standalone script (python tests/test_narrate.py) or via pytest. The cache and
envelope tests require the model artifacts; run src/train/train.py first.
"""
import json
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import llm, narrate as narrate_module
from src.core.narrate import build_messages, narrate

SAMPLE_PREDICTION = {
    "intent_score": 0.7905,
    "next_best_action": {
        "action": "checkout_nudge",
        "message": "Offer a free-shipping threshold and streamlined checkout to close.",
    },
    "drivers": [
        {"feature": "ExitRates", "value": 0.010526316, "contribution": 0.4842, "direction": "up"},
        {"feature": "Month", "value": "Nov", "contribution": 0.4512, "direction": "up"},
        {"feature": "total_duration", "value": 645.0, "contribution": -0.2705, "direction": "down"},
        {"feature": "VisitorType", "value": "New_Visitor", "contribution": 0.1288, "direction": "up"},
    ],
}


def _sample_features():
    samples = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "sample_sessions.json").read_text()
    )
    return samples[0]["features"]


@contextmanager
def _llm_stub(base_url, model, chat=None):
    """Temporarily override the transport module's endpoint settings and chat call."""
    saved = (llm.LLM_BASE_URL, llm.LLM_MODEL, llm.chat)
    llm.LLM_BASE_URL, llm.LLM_MODEL = base_url, model
    if chat is not None:
        llm.chat = chat
    try:
        yield
    finally:
        llm.LLM_BASE_URL, llm.LLM_MODEL, llm.chat = saved


def test_build_messages_pure():
    messages = build_messages(SAMPLE_PREDICTION, {})
    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert "79%" in user
    assert "high intent" in user
    assert "free-shipping threshold" in user
    assert "Exit rate = 1.1%" in user
    assert "Month = November" in user
    assert "Total session time = 645s" in user
    assert "new visitor" in user
    assert "pushes the score up" in user and "pushes the score down" in user


def test_unconfigured_returns_disabled():
    with _llm_stub("", ""):
        result = narrate(_sample_features())
    assert result == {"enabled": False, "narrative": None}


def test_narrate_caches_successes():
    calls = {"n": 0}

    def fake_chat(messages, **kwargs):
        calls["n"] += 1
        return "A short plain-language summary."

    narrate_module._generate.cache_clear()
    try:
        with _llm_stub("stub", "stub", chat=fake_chat):
            first = narrate(_sample_features())
            second = narrate(_sample_features())
    finally:
        narrate_module._generate.cache_clear()

    assert first == {"enabled": True, "narrative": "A short plain-language summary."}
    assert second == first
    assert calls["n"] == 1, f"expected one upstream call (cache hit), got {calls['n']}"


def main():
    test_build_messages_pure()
    test_unconfigured_returns_disabled()
    test_narrate_caches_successes()
    print("PASS: narrative prompt, disabled envelope, and success caching all behave.")


if __name__ == "__main__":
    main()
