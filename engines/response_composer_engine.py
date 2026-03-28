"""
Production-grade Response Composer Engine.
Generates natural, persuasive, context-aware replies using all agent outputs.
Arabic-first quality, Egypt/Gulf-friendly tone, variation for repeated contexts.
"""
from __future__ import annotations

from typing import Optional

from engines.lang_utils import detect_response_language

# Variation hints for repeated contexts - avoid robotic repetition
# Keyed by CTA; when we recently asked same thing, suggest alternate phrasing
VARIATION_HINTS_AR = {
    "ask_budget": "استخدم صياغة مختلفة تماماً عن آخر رسالة. لا تكرر 'ما هي ميزانيتك' أو 'كم ميزانيتك'. جرب: نطاق أسعار، ميزانية تقريبية، حدود الاستثمار.",
    "ask_location": "صياغة جديدة للمنطقة. تجنب تكرار 'أي منطقة'. جرب: المنطقة المفضلة، أين تفضل، نطاق جغرافي.",
    "ask_property_type": "صياغة مختلفة عن نوع العقار. لا تكرر 'شقة أم فيلا'. جرب: نوع الوحدة، نمط السكن.",
    "ask_bedrooms": "صياغة جديدة لعدد الغرف. تجنب التكرار الحرفي.",
    "propose_visit": "اقتراح المعاينة بصياغة مختلفة عن آخر مرة. تنويع: متى يناسبك، أي يوم، زيارة الموقع.",
    "recommend_projects": "عرض المشاريع بصياغة متنوعة. لا تكرر نفس الافتتاحية.",
    "nurture": "محتوى رعاية بصياغة جديدة. تنويع الافتتاحية والإغلاق.",
}

VARIATION_HINTS_EN = {
    "ask_budget": "Use a completely different phrasing than the last message. Don't repeat 'what is your budget'. Try: price range, approximate budget, investment limits.",
    "ask_location": "New phrasing for area. Avoid repeating 'which area'. Try: preferred area, where you'd like, geographic range.",
    "ask_property_type": "Different phrasing for property type. Don't repeat 'apartment or villa'. Try: unit type, living style.",
    "ask_bedrooms": "New phrasing for bedroom count. Avoid literal repetition.",
    "propose_visit": "Suggest viewing with different phrasing. Vary: when works for you, which day, site visit.",
    "recommend_projects": "Present projects with varied phrasing. Don't repeat the same opener.",
    "nurture": "Nurture content with fresh phrasing. Vary opener and closing.",
}


def _detect_recent_cta_and_variation(
    conversation_history: list,
    current_cta: str,
) -> tuple[str, str]:
    """
    Check if we recently used same CTA. Return (variation_hint_ar, variation_hint_en).
    """
    if not conversation_history or not current_cta:
        return "", ""
    recent = list(conversation_history or [])[-4:]
    for msg in reversed(recent):
        role = msg.get("role", "")
        content = (msg.get("content") or "").lower()
        if role != "assistant":
            continue
        # Heuristic: if last assistant message asks about budget, we may be repeating
        budget_terms = ["ميزانيت", "ميزانية", "budget", "سعر", "حد أقصى", "كم", "نطاق"]
        loc_terms = ["منطقة", "موقع", "location", "أين", "where"]
        if any(t in content for t in budget_terms) and current_cta == "ask_budget":
            return VARIATION_HINTS_AR.get("ask_budget", ""), VARIATION_HINTS_EN.get("ask_budget", "")
        if any(t in content for t in loc_terms) and current_cta == "ask_location":
            return VARIATION_HINTS_AR.get("ask_location", ""), VARIATION_HINTS_EN.get("ask_location", "")
    return "", ""


def _build_reasoning_summary(
    *,
    intent: dict,
    strategy: dict,
    persuasion: dict,
    journey_stage: dict,
    cta: str,
    composed_from: list[str],
) -> str:
    """Build short reasoning summary for operator UI."""
    parts = []
    if strategy.get("approach"):
        parts.append(f"approach={strategy['approach']}")
    if journey_stage.get("stage"):
        parts.append(f"stage={journey_stage['stage']}")
    if cta:
        parts.append(f"cta={cta}")
    if persuasion.get("objection_type"):
        parts.append(f"objection={persuasion['objection_type']}")
    if intent.get("primary"):
        parts.append(f"intent={intent['primary']}")
    if composed_from:
        parts.append(f"sources={','.join(composed_from[:4])}")
    return " | ".join(parts)[:300]


def compose_sales_response(
    user_message: str,
    *,
    intent: dict,
    memory: dict,
    qualification: dict,
    retrieval: dict,
    recommendation: dict,
    strategy: dict,
    persuasion: dict,
    conversation_plan: dict,
    journey_stage: dict,
    conversation_history: list[dict] | None = None,
    has_verified_pricing: bool = False,
    use_llm: bool = True,
    lang: str | None = None,
    channel: str = "web",
) -> tuple[str, str, str]:
    """
    Compose natural sales response.
    Returns: (reply_text, cta, reasoning_summary_for_operator).
    """
    history = conversation_history or []
    detected_lang = lang or detect_response_language(user_message)
    cta = strategy.get("recommended_cta") or persuasion.get("preferred_cta") or strategy.get("next_best_action") or "nurture"
    if persuasion.get("objection_type"):
        cta = persuasion.get("preferred_cta") or "address_objection"

    # Objection path: use objection library, then enhance with persuasion
    if strategy.get("objection_key") or persuasion.get("objection_type"):
        from engines.objection_library import get_objection_response, get_follow_up
        obj_map = {
            "price_too_high": "price_too_high",
            "unsure_about_area": "location_concern",
            "location_concern": "location_concern",
            "comparing_projects": "comparing_projects",
            "wants_more_time": "waiting_hesitation",
            "waiting_hesitation": "waiting_hesitation",
            "investment_value_concern": "investment_uncertainty",
            "investment_uncertainty": "investment_uncertainty",
            "delivery_concerns": "delivery_concerns",
            "financing_concerns": "payment_plan_mismatch",
            "payment_plan_mismatch": "payment_plan_mismatch",
            "trust_credibility": "trust_credibility",
        }
        pers_type = persuasion.get("objection_type") or strategy.get("objection_key", "price_too_high")
        lib_key = obj_map.get(pers_type, "price_too_high")
        reply = get_objection_response(lib_key, detected_lang)
        follow = get_follow_up(lib_key, detected_lang)
        if follow:
            reply += f" {follow}"
        from engines.persuasion import get_persuasive_points
        pers_type = persuasion.get("objection_type") or strategy.get("objection_key", "price_too_high")
        pts = get_persuasive_points(pers_type, detected_lang)
        if pts and len(reply) < 400:
            sep = " — " if detected_lang == "ar" else " — "
            reply += f"{sep}{pts[0]}"
        reasoning = _build_reasoning_summary(
            intent=intent, strategy=strategy, persuasion=persuasion,
            journey_stage=journey_stage, cta=cta, composed_from=["objection_library", "persuasion"],
        )
        from engines.response_sanitizer import sanitize_customer_response
        cleaned = sanitize_customer_response(reply)
        return cleaned if cleaned else reply, cta, reasoning

    # Normal sales path: build rich prompt and call sales engine or LLM
    def _retrieval_context(sources: list, summary: str) -> str:
        out = []
        for s in (sources or [])[:5]:
            title = s.get("document_title", "") or ""
            snip = (s.get("content_snippet") or "")[:150] if s.get("content_snippet") else ""
            out.append(f"[{title}]" + (f": {snip}" if snip else ""))
        return "\n\n".join(out).strip() or (summary or "")

    retrieval_ctx = _retrieval_context(
        retrieval.get("retrieval_sources", []),
        retrieval.get("structured_summary", ""),
    )
    var_ar, var_en = _detect_recent_cta_and_variation(history, cta)
    variation_hint = var_ar if detected_lang == "ar" else var_en

    from engines.sales_engine import generate_sales_response
    from engines.response_sanitizer import sanitize_customer_response

    reply = generate_sales_response(
        user_message,
        mode="warm_lead",
        conversation_history=history,
        qualification=qualification,
        retrieval_context=retrieval_ctx,
        has_verified_pricing=has_verified_pricing,
        conversation_plan={
            "sales_objective_now": conversation_plan.get("sales_objective_now", ""),
            "best_next_question_or_suggestion": conversation_plan.get("best_next_question_or_suggestion", ""),
        },
        variation_hint=variation_hint,
        use_llm=use_llm,
        channel=channel,
    )

    reply = sanitize_customer_response(reply)
    if not reply and detected_lang == "ar":
        reply = "أهلاً! سعيد بتواصلك. لو تحب نضيق الخيارات: ما الميزانية التقريبية والمنطقة التي تفضلها؟"
    elif not reply:
        reply = "Hello! Glad you reached out. To narrow options: what's your approximate budget and preferred area?"

    # If we have variation hint and LLM was used, the prompt already had it. If not LLM, try to vary fallback
    if not use_llm and variation_hint:
        # Fallback templates - pick alternate opener when repeating
        from engines.templates import get_template
        tpl = get_template("warm_lead")
        openers_ar = [
            "أهلاً! سعيد بتواصلك. لمساعدتك بشكل أفضل: ما المساحة والمنطقة المفضلة لديك؟",
            "مرحباً! يسعدني مساعدتك. لو تحب نضيق الخيارات: ما الميزانية التقريبية والمنطقة التي تفضلها؟",
            "أهلاً وسهلاً! عشان أرشح لك الأنسب: هل عندك نطاق سعري معين ومنطقة مفضلة؟",
        ]
        openers_en = [
            "Hello! Glad you reached out. To help better: what size and area are you looking for?",
            "Hi! Happy to help. To narrow options: what's your approximate budget and preferred area?",
            "Welcome! To recommend the best fit: do you have a price range and preferred location?",
        ]
        # Use message length / simple hash to pick variant when no LLM
        idx = hash(user_message[-20:] if len(user_message) > 20 else user_message) % 3
        if detected_lang == "ar":
            reply = openers_ar[idx % len(openers_ar)]
        else:
            reply = openers_en[idx % len(openers_en)]

    reasoning = _build_reasoning_summary(
        intent=intent,
        strategy=strategy,
        persuasion=persuasion,
        journey_stage=journey_stage,
        cta=cta,
        composed_from=["sales_engine", "conversation_plan", "retrieval"],
    )
    return reply, cta, reasoning


def compose_support_response(
    user_message: str,
    *,
    intent: dict,
    routing: dict,
    conversation_history: list[dict] | None = None,
    use_llm: bool = True,
    channel: str = "web",
) -> tuple[str, str, str]:
    """Compose support response. Returns (reply_text, cta, reasoning_summary)."""
    from engines.support_engine import generate_support_response
    support_cat = routing.get("queue", "") or routing.get("category", "")
    mode = "angry_customer" if routing.get("escalation_ready") else "existing_customer_support"
    reply = generate_support_response(
        user_message,
        mode=mode,
        category=support_cat,
        is_angry=False,
        conversation_history=conversation_history or [],
        use_llm=use_llm,
        channel=channel,
    )
    cta = "move_to_human" if routing.get("escalation_ready") else "nurture"
    reasoning = f"support | category={support_cat} | mode={mode} | cta={cta}"
    return reply, cta, reasoning[:300]


def compose_recommendation_response(
    *,
    recommendation: dict,
    lang: str = "ar",
    use_llm: bool = True,
) -> tuple[str, str, str]:
    """Compose recommendation response. Returns (reply_text, cta, reasoning_summary)."""
    from engines.response_builder import build_recommendation_response
    from engines.recommendation_engine import ProjectMatch
    from decimal import Decimal

    reply = recommendation.get("response_text", "")
    matches_data = recommendation.get("matches", []) or recommendation.get("top_recommendations", [])
    if not reply and matches_data:
        pm_list = [
            ProjectMatch(
                project_id=m.get("project_id", 0),
                project_name=m.get("project_name", ""),
                location=m.get("location", ""),
                price_min=Decimal(str(m["price_min"])) if m.get("price_min") is not None else None,
                price_max=Decimal(str(m["price_max"])) if m.get("price_max") is not None else None,
                rationale=m.get("rationale", ""),
                fit_score=m.get("fit_score", 0),
                match_reasons=m.get("match_reasons", []),
                confidence=m.get("confidence", 0),
                trade_offs=m.get("trade_offs", []),
                has_verified_pricing=m.get("has_verified_pricing", False),
            )
            for m in matches_data
        ]
        reply = build_recommendation_response(pm_list, lang=lang)
    cta = "recommend_projects"
    reasoning = f"recommendation | matches={len(matches_data)} | cta={cta}"
    return reply or "", cta, reasoning[:300]
