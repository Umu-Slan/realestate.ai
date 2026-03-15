"""
OpenAI-compatible LLM client. Supports timeout for graceful failure handling.
"""
from django.conf import settings
from openai import OpenAI

from core.adapters.llm import BaseLLMClient


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def chat_completion(self, messages: list[dict], timeout: int = 30, **kwargs) -> str:
        to = kwargs.pop("timeout", timeout)
        resp = self.client.chat.completions.create(
            model=getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
            messages=messages,
            timeout=to,
            **kwargs,
        )
        if resp.choices:
            return resp.choices[0].message.content or ""
        return ""
