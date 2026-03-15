"""
Mock LLM client for demo mode.
"""
from core.adapters.llm import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Returns canned responses for demo."""

    def chat_completion(self, messages: list[dict], **kwargs) -> str:
        last = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not last:
            return "مرحباً! كيف يمكنني مساعدتك اليوم؟"
        text = last.get("content", "").lower()
        if "سعر" in text or "price" in text:
            return "للمعلومات الدقيقة عن الأسعار، يرجى التواصل مع فريق المبيعات. يمكننا تقديم نطاقات تقريبية بناءً على المشروع."
        if "شقة" in text or "apartment" in text:
            return "لدينا عدة مشاريع سكنية. أخبرني بمساحتك المفضلة والموقع لأساعدك بشكل أفضل."
        return "شكراً على تواصلكم. كيف يمكنني مساعدتك في العثور على العقار المناسب؟"
