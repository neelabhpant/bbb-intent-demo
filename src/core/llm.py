"""Thin client for a chat-completions-style HTTP model endpoint.

Generic transport only: messages in, assistant text out. All endpoint specifics (base
URL, key, model name) come from the environment via src/config.py, so the same client
points at any compatible hosted endpoint without code changes. This is another swappable
edge: when porting, only LLM_BASE_URL / LLM_API_KEY / LLM_MODEL change (see PORTING.md).
The scoring path never imports this module.
"""
import requests

from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS


class LLMError(RuntimeError):
    """Raised when the model endpoint is unreachable, times out, or returns junk."""


def is_configured() -> bool:
    """True when the environment provides enough to call a model endpoint."""
    return bool(LLM_BASE_URL and LLM_MODEL)


def chat(messages, *, temperature=0.2, max_tokens=220, timeout=None) -> str:
    """Send a chat-completions request and return the assistant's text.

    Every failure mode is wrapped in LLMError. Error messages carry the HTTP status
    code only, never response bodies, so nothing sensitive can land in logs.
    """
    if not is_configured():
        raise LLMError("Model endpoint is not configured (set LLM_BASE_URL and LLM_MODEL).")

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            json=body,
            headers=headers,
            timeout=timeout if timeout is not None else LLM_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Model endpoint request failed: {type(exc).__name__}") from exc

    if not response.ok:
        raise LLMError(f"Model endpoint returned HTTP {response.status_code}.")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("Model endpoint returned an unexpected response shape.") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMError("Model endpoint returned an empty completion.")
    return content.strip()
