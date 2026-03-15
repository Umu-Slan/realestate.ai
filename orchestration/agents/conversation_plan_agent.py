"""
Conversation Planning Agent - creates internal conversation plan before final response.
Synthesizes: what we know, what we still need, sales objective, best next question/suggestion.
Plans are internal—never exposed to end users.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import ConversationPlanAgentOutput

# Field labels for human-readable plan (internal only)
FIELD_LABELS = {
    "budget": "Budget range",
    "location": "Location preference",
    "project_preference": "Project interest",
    "property_type": "Property type",
    "bedrooms": "Bedroom count",
    "purpose": "Purpose (residence/investment)",
    "urgency": "Urgency/timeline",
}


def _build_what_we_know(qualification: dict, memory: dict, intent: dict) -> list[str]:
    """Derive known facts from qualification, memory, intent."""
    known: list[str] = []
    q = qualification or {}
    mem = memory or {}
    i = intent or {}

    if q.get("budget_min") or q.get("budget_max"):
        bmin = q.get("budget_min") or ""
        bmax = q.get("budget_max") or ""
        known.append(f"Budget: {bmin}-{bmax} EGP")
    if q.get("location_preference"):
        known.append(f"Location: {q['location_preference']}")
    if q.get("project_preference"):
        known.append(f"Project interest: {q['project_preference']}")
    if q.get("property_type"):
        known.append(f"Property type: {q['property_type']}")
    if q.get("bedrooms") is not None:
        known.append(f"Bedrooms: {q['bedrooms']}")
    if q.get("purpose"):
        known.append(f"Purpose: {q['purpose']}")
    if q.get("urgency"):
        known.append(f"Urgency: {q['urgency']}")

    key_facts = mem.get("key_facts") or []
    for f in key_facts[:5]:
        if f and f not in known:
            known.append(str(f)[:80])

    customer_type = mem.get("customer_type_hint") or ""
    if customer_type and customer_type != "new_lead":
        known.append(f"Customer type: {customer_type}")

    intent_primary = (i.get("primary") or "").strip()
    if intent_primary and intent_primary != "other":
        known.append(f"Current intent: {intent_primary}")

    return known[:15]


def _build_what_we_still_need(qualification: dict, response_mode: str, is_support: bool) -> list[str]:
    """Derive missing info from qualification. Empty when support mode."""
    if response_mode == "support" or is_support:
        return []
    missing = qualification.get("missing_fields") or []
    labels = []
    for m in missing[:10]:
        label = FIELD_LABELS.get(m, m.replace("_", " ").title())
        labels.append(label)
    return labels


def _build_sales_objective(
    strategy: dict,
    journey: dict,
    persuasion: dict,
    response_mode: str,
    is_support: bool,
) -> str:
    """Derive current sales objective from strategy, journey, persuasion.
    Returns NATURAL-LANGUAGE guidance for the LLM, never internal strategy labels.
    """
    if response_mode == "support" or is_support:
        return "Help the customer resolve their support issue warmly and professionally"

    obj = strategy.get("objective") or strategy.get("next_best_action") or ""
    if obj and not _is_internal_strategy_label(obj):
        return obj[:200]

    if persuasion.get("objection_type"):
        return "Address their concern empathetically, then naturally suggest a next step"

    # Map internal next_sales_move to natural guidance - NEVER pass raw internal labels
    next_move = (journey.get("next_sales_move") or "").strip()
    if next_move:
        natural = _internal_to_natural_objective(next_move)
        if natural:
            return natural[:200]

    return "Warmly engage, qualify their needs with natural questions, and nurture the relationship"


def _is_internal_strategy_label(text: str) -> bool:
    """True if text is an internal strategy label (e.g. 'Share value proposition...')."""
    from engines.response_sanitizer import is_internal_objective
    return is_internal_objective(text)


def _internal_to_natural_objective(internal: str) -> str:
    """Convert internal next_sales_move to natural LLM guidance."""
    internal_lower = internal.lower()
    natural_map = {
        "share value proposition and qualify budget/location": "Warmly welcome them and naturally ask about budget range and preferred area",
        "gather project preference": "Ask which type of project or area interests them",
        "offer property overviews and narrow preferences": "Share a brief overview of options and ask what matters most to them",
        "send project details and schedule visit": "Offer to share project details and suggest a site visit",
        "share brochures and arrange site visit": "Offer brochures and arrange a visit when they are ready",
        "confirm visit slot and send directions": "Confirm their preferred visit time and provide directions",
        "present offers and facilitate decision": "Present relevant options and help them decide",
        "guide through booking steps": "Guide them through the booking process step by step",
        "follow up on handover": "Follow up on handover and satisfaction",
        "resolve issue and maintain relationship": "Resolve the issue warmly and maintain the relationship",
        "continue qualification and nurture": "Continue to qualify their needs and nurture the relationship",
    }
    for k, v in natural_map.items():
        if k in internal_lower:
            return v
    # Fallback: don't pass raw internal text
    if _is_internal_strategy_label(internal):
        return "Advance the conversation naturally with one helpful question or suggestion"
    return internal[:200]


def _build_best_next_question(
    strategy: dict,
    journey: dict,
    persuasion: dict,
    qualification: dict,
    response_mode: str,
    is_support: bool,
    lang: str = "ar",
) -> str:
    """Derive best next question or suggestion to advance conversation."""
    if response_mode == "support" or is_support:
        return "Offer resolution and next steps"

    if persuasion.get("objection_type"):
        cta = persuasion.get("preferred_cta") or "address_objection"
        if cta == "address_objection":
            return "Address concern directly, then suggest next step"

    cta = strategy.get("recommended_cta") or strategy.get("next_best_action") or "nurture"

    # Map CTA to concrete question/suggestion (internal guidance for LLM)
    # CRITICAL: When budget+location known, NEVER suggest asking for them - advance to consideration
    has_budget = bool(qualification.get("budget_min") or qualification.get("budget_max"))
    has_location = bool(qualification.get("location_preference"))
    if has_budget and has_location:
        return "ميزانيتك ومنطقتك المفضلة تفتح عدة خيارات جيدة. اسأل: هل تفضل شقة جاهزة للاستلام أم مشروع تحت الإنشاء بالتقسيط؟ ثم قدم المشاريع المطابقة."

    suggestions_ar = {
        "ask_budget": "ما هي ميزانيتك أو نطاق الأسعار الذي تبحث عنه؟",
        "ask_location": "أي منطقة تفضل؟",
        "ask_property_type": "هل تبحث عن شقة أم فيلا؟",
        "ask_bedrooms": "كم غرفة نوم تحتاج؟",
        "recommend_projects": "تقديم المشاريع المطابقة لمعاييره",
        "propose_visit": "اقتراح زيارة موقع لعرض الوحدة",
        "create_urgency": "توضيح توفر الوحدات والخطوة التالية",
        "address_objection": "معالجة الاعتراض ثم اقتراح الخطوة التالية",
        "move_to_human": "ربط العميل بمندوب مبيعات",
        "nurture": "مشاركة محتوى مفيد وطلب التفضيلات",
    }
    suggestions_en = {
        "ask_budget": "What is your budget or price range?",
        "ask_location": "Which area do you prefer?",
        "ask_property_type": "Are you looking for an apartment or villa?",
        "ask_bedrooms": "How many bedrooms do you need?",
        "recommend_projects": "Present matching projects",
        "propose_visit": "Suggest site visit to view the unit",
        "create_urgency": "Clarify availability and next step",
        "address_objection": "Address objection then suggest next step",
        "move_to_human": "Connect customer with sales rep",
        "nurture": "Share helpful content and ask preferences",
    }
    lookup = suggestions_ar if lang == "ar" else suggestions_en
    if has_budget and has_location and cta in ("recommend_projects", "recommend_project"):
        return suggestions_ar.get("recommend_projects", "") if lang == "ar" else "With your budget and area, ask: ready-to-move or under-construction? Then present matching projects."
    return lookup.get(cta, lookup.get("nurture", ""))


class ConversationPlanAgent:
    name = "conversation_plan"

    def run(self, context: AgentContext) -> AgentResult:
        """Build conversation plan from all upstream agent outputs."""
        try:
            qualification = context.get_qualification()
            memory = context.get_memory()
            intent = context.intent_output or {}
            strategy = context.sales_strategy_output or {}
            journey = context.journey_stage_output or {}
            persuasion = context.persuasion_output or {}
            response_mode = context.response_mode or ""
            is_support = bool(intent.get("is_support"))
            lang = context.lang or "ar"

            what_we_know = _build_what_we_know(qualification, memory, intent)
            what_we_still_need = _build_what_we_still_need(
                qualification, response_mode, is_support
            )
            sales_objective_now = _build_sales_objective(
                strategy, journey, persuasion, response_mode, is_support
            )
            best_next = _build_best_next_question(
                strategy, journey, persuasion, qualification,
                response_mode, is_support, lang
            )

            output = ConversationPlanAgentOutput(
                what_we_know=what_we_know,
                what_we_still_need=what_we_still_need,
                sales_objective_now=sales_objective_now,
                best_next_question_or_suggestion=best_next,
            )
            context.conversation_plan_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "has_known": len(what_we_know) > 0,
                    "has_need": len(what_we_still_need) > 0,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
