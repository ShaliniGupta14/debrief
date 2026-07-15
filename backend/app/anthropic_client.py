"""Lazy singleton Anthropic client for the API process (calibration runs
synchronously within a request, unlike per-call judging which happens in
the worker). Returns None when no key is configured rather than raising,
so callers decide how to respond (503, skip, etc.) instead of every
caller needing its own try/except around client construction."""

import anthropic

from app.config import get_settings

_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic | None:
    global _client
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client
