"""
LLM client for intelligence - adapter-ready, OpenAI-based by default.
"""
import json
from typing import Any, Optional

from django.conf import settings


def _get_client():
    """Lazy import to avoid startup cost when LLM not used."""
    try:
        from openai import OpenAI
        return OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", "") or None)
    except ImportError:
        return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
) -> dict[str, Any] | None:
    """
    Call LLM with structured output. Returns parsed JSON or None on failure.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        return None

    client = _get_client()
    if not client:
        return None

    model = model or getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    try:
        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content if resp.choices else None
        if content:
            return json.loads(content)
    except Exception:
        pass
    return None
