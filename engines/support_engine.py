"""
Support Conversation Engine - calm, structured, escalate when needed.
"""
from engines.templates import get_system_prompt, get_template
from engines.lang_utils import detect_response_language


def _build_support_context(
    category: str = "",
    is_angry: bool = False,
    channel: str = "web",
) -> str:
    from engines.channel_voice import format_channel_context_for_llm

    parts = [format_channel_context_for_llm(channel)]
    if category:
        parts.append(f"Issue category: {category}")
    if is_angry:
        parts.append("Customer is frustrated. Acknowledge first, escalate if needed.")
    return "\n".join(parts) if parts else ""


def generate_support_response(
    user_message: str,
    *,
    mode: str = "existing_customer_support",
    category: str = "",
    is_angry: bool = False,
    conversation_history: list[dict] | None = None,
    use_llm: bool = True,
    channel: str = "web",
) -> str:
    """
    Generate support response. Calm, respectful, collect info, escalate when sensitive.
    """
    lang = detect_response_language(user_message)
    history = conversation_history or []

    system = get_system_prompt(mode)
    context = _build_support_context(category=category, is_angry=is_angry, channel=channel)
    if context:
        system += f"\n\nContext:\n{context}"

    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:
        messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    if use_llm:
        try:
            from core.adapters.llm import get_llm_client
            return get_llm_client().chat_completion(messages)
        except Exception:
            pass

    template = get_template("angry_customer" if is_angry else mode)
    if lang == "ar":
        return template.opening_ar or "مرحباً. كيف يمكنني مساعدتك؟"
    return template.opening_en or "Hello. How can I help you?"
