"""
LLM adapter. Supports OpenAI-compatible APIs. Mock in demo mode.
"""
from django.conf import settings


def get_llm_client():
    """Return LLM client — real or mock based on DEMO_MODE."""
    if getattr(settings, "DEMO_MODE", False):
        from core.adapters.llm_mock import MockLLMClient
        return MockLLMClient()
    from core.adapters.llm_openai import OpenAILLMClient
    return OpenAILLMClient()


class BaseLLMClient:
    """Base contract for LLM clients."""

    def chat_completion(self, messages: list[dict], **kwargs) -> str:
        """Return assistant message content."""
        raise NotImplementedError
