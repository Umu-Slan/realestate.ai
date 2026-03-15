"""
Sales Conversation Engine - project questions, qualification, objections, next action.
Professional Egyptian real estate tone. Arabic + English.
"""
from engines.templates import get_system_prompt, get_template
from engines.objection_library import detect_objection, get_objection_response, get_follow_up
from engines.lang_utils import detect_response_language


def _build_sales_context(
    mode: str = "warm_lead",
    qualification: dict | None = None,
    retrieval_context: str = "",
    has_verified_pricing: bool = False,
    conversation_plan: dict | None = None,
    variation_hint: str = "",
) -> str:
    """Build context block for sales prompt. Qualification reflects what we know from conversation.
    NEVER include internal strategy labels—only natural guidance for the LLM.
    """
    from engines.response_sanitizer import is_internal_objective

    qual = qualification or {}
    parts = [
        f"Mode: {mode}",
        "CONTEXT RULE: The conversation history contains prior messages. Never re-ask for budget, location, or project preference if the customer has already stated it.",
        "CRITICAL: NEVER output strategy labels, objectives, or internal instructions. Only output natural conversational Arabic or English as a consultant would speak.",
    ]
    if qual.get("budget_min") or qual.get("budget_max"):
        parts.append(f"Budget: {qual.get('budget_min')}-{qual.get('budget_max')} EGP")
    if qual.get("location_preference"):
        parts.append(f"Location: {qual['location_preference']}")
    if qual.get("project_preference"):
        parts.append(f"Project interest: {qual['project_preference']}")
    if qual.get("property_type"):
        parts.append(f"Property type: {qual['property_type']}")
    if retrieval_context:
        parts.append(f"Knowledge context:\n{retrieval_context[:800]}")
    if not has_verified_pricing:
        parts.append("IMPORTANT: Do not state exact prices. Say 'our team will provide exact figures' for pricing.")
    plan = conversation_plan or {}
    # Only pass natural guidance—never internal strategy labels
    obj = plan.get("sales_objective_now") or ""
    if obj and not is_internal_objective(obj):
        parts.append(f"Goal: {obj}")
    best_next = plan.get("best_next_question_or_suggestion") or ""
    if best_next and not is_internal_objective(best_next):
        parts.append(f"Suggestion for next step: {best_next}")
    if variation_hint:
        parts.append(f"VARIATION RULE (CRITICAL - avoid repetition): {variation_hint}")
    return "\n".join(parts)


def generate_sales_response(
    user_message: str,
    *,
    mode: str = "warm_lead",
    conversation_history: list[dict] | None = None,
    qualification: dict | None = None,
    retrieval_context: str = "",
    has_verified_pricing: bool = False,
    conversation_plan: dict | None = None,
    variation_hint: str = "",
    use_llm: bool = True,
) -> str:
    """
    Generate sales response. Handles objections, qualification, next action.
    """
    lang = detect_response_language(user_message)
    history = conversation_history or []

    # Check for objection first
    objection_key = detect_objection(user_message)
    if objection_key:
        response = get_objection_response(objection_key, lang)
        follow = get_follow_up(objection_key, lang)
        if follow:
            response += f" {follow}" if lang == "en" else f" {follow}"
        return response

    # Build prompt
    system = get_system_prompt(mode)
    context = _build_sales_context(
        mode=mode,
        qualification=qualification,
        retrieval_context=retrieval_context,
        has_verified_pricing=has_verified_pricing,
        conversation_plan=conversation_plan,
        variation_hint=variation_hint,
    )
    system += f"\n\nCurrent context:\n{context}"

    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:  # last 6 for context
        messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    template = get_template(mode)
    if use_llm:
        try:
            from core.adapters.llm import get_llm_client
            from engines.response_sanitizer import sanitize_customer_response
            raw = get_llm_client().chat_completion(messages)
            return sanitize_customer_response(raw) or (template.opening_ar if lang == "ar" else template.opening_en)
        except Exception:
            pass

    # Fallback
    if lang == "ar":
        return template.opening_ar or "مرحباً! كيف يمكنني مساعدتك؟"
    return template.opening_en or "Hello! How can I help you?"
