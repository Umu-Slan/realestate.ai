"""
Sales Strategy Agent - decides best next conversational move.
Uses: intent, buyer stage, lead score, retrieved context, recommendations, memory.
Returns: strategy, objective, persuasive_angle, recommended_cta.
Avoids repetitive generic next steps via conversation-history awareness.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import SalesStrategyAgentOutput, ScoringSummary, SALES_CTA_OPTIONS

# Persuasive angles per CTA - natural, non-robotic
PERSUASIVE_ANGLES = {
    "ask_budget": "Understanding your budget helps us show only options that fit.",
    "ask_location": "Knowing your preferred area lets us highlight the best matches there.",
    "ask_property_type": "Whether apartment or villa, we'll tailor the search to your preference.",
    "ask_bedrooms": "How many bedrooms do you need? That narrows down the best units.",
    "recommend_projects": "Based on what you've shared, these projects match your criteria.",
    "propose_visit": "A site visit will give you a real sense of the space and community.",
    "create_urgency": "Units in this segment tend to move quickly—worth considering soon.",
    "address_objection": "I understand your concern. Let me address that directly.",
    "move_to_human": "I'll connect you with our team for personalized assistance.",
    "nurture": "Here's some helpful content while you explore your options.",
}

OBJECTIVES = {
    "ask_budget": "Qualify budget to filter options",
    "ask_location": "Qualify location preference",
    "ask_property_type": "Qualify property type",
    "ask_bedrooms": "Qualify bedroom requirement",
    "recommend_projects": "Present matched projects",
    "propose_visit": "Schedule site visit",
    "create_urgency": "Encourage timely decision",
    "address_objection": "Resolve objection to move forward",
    "move_to_human": "Hand off to human agent",
    "nurture": "Build relationship with content",
}


def _recently_asked(conversation_history: list, field: str) -> bool:
    """Check if we recently asked for this field (anti-repetition)."""
    keywords = {
        "budget": ["ميزانيت", "ميزانية", "budget", "سعر", "حد أقصى", "حد أقصي", "ما هو", "كم", "تستطيع"],
        "location": ["منطقة", "موقع", "location", "مكان", "أين", "where", "area"],
        "property_type": ["نوع العقار", "شقة", "فيلا", "property type", "apartment", "villa"],
        "bedrooms": ["غرف", "غرفة", "bedroom", "غرف نوم"],
    }
    terms = keywords.get(field, [])
    if not terms:
        return False
    recent = (conversation_history or [])[-4:]
    for msg in reversed(recent):
        role = msg.get("role", "")
        content = (msg.get("content") or "").lower()
        if role == "assistant" and any(t.lower() in content for t in terms):
            return True
    return False


def _compute_recommended_cta(
    *,
    intent: dict,
    qualification: dict,
    routing: dict,
    next_act_action: str,
    objection_key: str,
    temperature: str,
    score: int,
    buyer_stage: str,
    has_recommendations: bool,
    conversation_history: list,
) -> str:
    """Map next action + context to CTA. NEVER ask for fields already known in qualification."""
    history = conversation_history or []
    missing = qualification.get("missing_fields") or []
    intent_primary = (intent.get("primary") or "").lower()
    stage = (buyer_stage or "").lower()

    # ResponseDecision rule: NEVER ask for a field already in memory
    has_budget = bool(qualification.get("budget_min") or qualification.get("budget_max"))
    has_location = bool(qualification.get("location_preference"))
    has_property_type = bool(qualification.get("property_type"))
    has_bedrooms = qualification.get("bedrooms") is not None

    def _would_ask_known(cta: str) -> bool:
        if cta == "ask_budget" and has_budget:
            return True
        if cta in ("ask_location", "ask_preferred_area") and has_location:
            return True
        if cta == "ask_property_type" and has_property_type:
            return True
        if cta == "ask_bedrooms" and has_bedrooms:
            return True
        return False

    if objection_key:
        return "address_objection"
    if routing.get("escalation_ready") or routing.get("force_escalation"):
        return "move_to_human"

    # Intent-driven
    if "visit" in intent_primary or "schedule" in intent_primary or "booking" in intent_primary:
        return "propose_visit"
    if ("brochure" in intent_primary or intent_primary == "brochure_request") and has_recommendations:
        return "recommend_projects"

    # Map next_action to CTA
    action_to_cta = {
        "ask_budget": "ask_budget",
        "ask_preferred_area": "ask_location",
        "send_brochure": "recommend_projects",
        "recommend_project": "recommend_projects",
        "propose_visit": "propose_visit",
        "request_scheduling": "propose_visit",
        "assign_sales_rep": "propose_visit",
        "create_support_case": "move_to_human",
        "escalate_to_human": "move_to_human",
        "nurture_content": "nurture",
        "clarify_intent": "nurture",
        "none": "nurture",
    }
    cta = action_to_cta.get(next_act_action, "nurture")

    # Anti-repetition: avoid re-asking recently asked
    if cta == "ask_budget" and _recently_asked(history, "budget"):
        cta = "ask_location" if "location" in missing and not _recently_asked(history, "location") else "nurture"
    elif cta == "ask_location" and _recently_asked(history, "location"):
        cta = "ask_property_type" if "property_type" in missing else "nurture"
    elif cta == "ask_property_type" and _recently_asked(history, "property_type"):
        cta = "ask_bedrooms" if qualification.get("bedrooms") is None else "recommend_projects"

    # Stage-based overrides
    if stage in ("shortlisting", "visit_planning", "negotiation") and temperature == "hot" and has_recommendations:
        cta = "propose_visit"
    elif stage == "consideration" and score >= 60 and has_recommendations:
        cta = "recommend_projects"
    elif temperature == "hot" and score >= 75 and stage in ("visit_planning", "negotiation"):
        cta = "propose_visit"

    return cta if cta in SALES_CTA_OPTIONS else "nurture"


class SalesStrategyAgent:
    name = "sales_strategy"

    def run(self, context: AgentContext) -> AgentResult:
        """Decide sales approach, detect objections, determine next action."""
        try:
            from decimal import Decimal
            from engines.objection_library import detect_objection
            from orchestration.next_action import compute_next_best_action
            from intelligence.services.scoring_engine import score_lead
            from intelligence.services.clarification_bypass import relax_clarification_routing_if_applicable
            from intelligence.services.routing import apply_routing_rules, classify_support_category
            from intelligence.schemas import QualificationExtraction, IntentResult, ScoringResult, ReasonCode

            intent_data = context.intent_output or {}
            qualification_data = context.get_qualification()
            memory = context.memory_output or {}
            customer_type = memory.get("customer_type_hint", "new_lead")

            q = QualificationExtraction(
                budget_min=Decimal(str(qualification_data["budget_min"])) if qualification_data.get("budget_min") else None,
                budget_max=Decimal(str(qualification_data["budget_max"])) if qualification_data.get("budget_max") else None,
                location_preference=qualification_data.get("location_preference", ""),
                project_preference=qualification_data.get("project_preference", ""),
                property_type=qualification_data.get("property_type", ""),
                urgency=qualification_data.get("urgency", ""),
                missing_fields=qualification_data.get("missing_fields", []),
                confidence=qualification_data.get("confidence", "unknown"),
            )
            intent = IntentResult(
                primary=intent_data.get("primary", "other"),
                secondary=intent_data.get("secondary", []),
                confidence=intent_data.get("confidence", 0),
                is_support=intent_data.get("is_support", False),
                is_spam=intent_data.get("is_spam", False),
                is_broker=intent_data.get("is_broker", False),
            )

            # Prefer Lead Qualification Agent score when available (production-grade scoring)
            scoring = None
            if qualification_data.get("lead_score") is not None and customer_type in ("new_lead", "returning_lead", "broker"):
                scoring = ScoringResult(
                    score=int(qualification_data.get("lead_score", 0)),
                    temperature=qualification_data.get("lead_temperature", "nurture"),
                    confidence=qualification_data.get("confidence", "medium"),
                    reason_codes=[ReasonCode(r.get("factor", ""), r.get("contribution", 0), r.get("note", "")) for r in (qualification_data.get("reasoning") or [])],
                    missing_fields=qualification_data.get("missing_fields", []) or [],
                    next_best_action=qualification_data.get("next_best_action", ""),
                    recommended_route="senior_sales" if qualification_data.get("lead_temperature") == "hot" else "sales" if qualification_data.get("lead_temperature") == "warm" else "nurture",
                )
            if scoring is None and customer_type in ("new_lead", "returning_lead", "broker"):
                scoring = score_lead(q, intent, is_returning=customer_type == "returning_lead")

            scoring_result = scoring or ScoringResult(
                score=0, temperature="nurture", confidence="unknown",
                next_best_action="", recommended_route="nurture",
            )
            routing_decision = apply_routing_rules(
                intent=intent,
                qualification=q,
                scoring=scoring_result,
                customer_type=customer_type,
                is_angry=getattr(context, "is_angry", False),
                exact_price_available=context.retrieval_output.get("has_verified_pricing", True)
                if context.retrieval_output
                else True,
            )
            routing_decision = relax_clarification_routing_if_applicable(
                routing_decision,
                intent,
                scoring_result,
                context.message_text or "",
                context.conversation_history or [],
            )
            support_category = ""
            if customer_type in ("support_customer", "existing_customer"):
                support_category = classify_support_category(intent)
                if hasattr(support_category, "value"):
                    support_category = support_category.value
            routing = {
                "route": routing_decision.route,
                "queue": routing_decision.queue,
                "requires_human_review": routing_decision.requires_human_review,
                "escalation_ready": routing_decision.escalation_ready,
                "quarantine": routing_decision.quarantine,
                "handoff_type": routing_decision.handoff_type,
                "safe_response_policy": routing_decision.safe_response_policy,
                "customer_type": customer_type,
            }
            if support_category:
                context.qualification_output = dict(context.qualification_output or {})
                context.qualification_output["support_category"] = support_category

            objection_key = detect_objection(context.message_text)
            approach = "nurture"
            if intent_data.get("is_support") or customer_type == "support_customer":
                approach = "support"
            elif scoring and scoring.temperature == "hot":
                approach = "convert"
            elif scoring and scoring.temperature == "warm":
                approach = "qualify"
            elif objection_key:
                approach = "objection_handling"

            buyer_stage = (
                (context.intent_output or {}).get("stage_hint", "")
                or (context.get_memory() or {}).get("journey_stage", "")
                or ""
            )
            next_act = compute_next_best_action(
                customer_type=customer_type,
                intent_primary=intent_data.get("primary", ""),
                missing_fields=qualification_data.get("missing_fields", []),
                score=scoring.score if scoring else 0,
                temperature=scoring.temperature if scoring else "nurture",
                routing=routing,
                requires_clarification=False,
                journey_stage=buyer_stage,
            )
            next_best_action = f"{next_act.action.value if hasattr(next_act.action, 'value') else next_act.action}: {next_act.reason}"

            has_recommendations = bool(
                (context.recommendation_output or {}).get("matches")
                or (context.property_matching_output or {}).get("matches")
            )
            recommended_cta = _compute_recommended_cta(
                intent=intent_data,
                qualification=qualification_data,
                routing=routing,
                next_act_action=next_act.action.value if hasattr(next_act.action, "value") else str(next_act.action),
                objection_key=objection_key,
                temperature=scoring.temperature if scoring else "nurture",
                score=scoring.score if scoring else 0,
                buyer_stage=buyer_stage,
                has_recommendations=has_recommendations,
                conversation_history=context.conversation_history or [],
            )
            strategy = approach
            objective = OBJECTIVES.get(recommended_cta, "")
            persuasive_angle = PERSUASIVE_ANGLES.get(recommended_cta, "")

            key_points = []
            if qualification_data.get("budget_min") or qualification_data.get("budget_max"):
                key_points.append("budget_known")
            if qualification_data.get("location_preference"):
                key_points.append("location_known")
            if objection_key:
                key_points.append(f"objection:{objection_key}")
            # Market context (only supported facts - no hallucination)
            market_ctx = getattr(context, "market_context_output", None) or {}
            market_tags = set()
            for _pid, ctx in (market_ctx.get("projects") or {}).items():
                if ctx.get("family_suitability"):
                    market_tags.add("market:family_suitable")
                if ctx.get("investment_suitability"):
                    market_tags.add("market:investment_friendly")
                if ctx.get("price_segment"):
                    market_tags.add(f"market:price_{ctx['price_segment']}")
                if ctx.get("demand_cues"):
                    for cue in ctx["demand_cues"][:2]:
                        market_tags.add(f"market:demand_{cue}")
            key_points.extend(sorted(market_tags))

            scoring_summary = None
            if scoring:
                scoring_summary = ScoringSummary(
                    score=scoring.score,
                    temperature=scoring.temperature,
                    confidence=scoring.confidence,
                    next_best_action=scoring.next_best_action,
                    recommended_route=scoring.recommended_route,
                    reason_codes=[{"factor": r.factor, "contribution": r.contribution, "note": r.note} for r in (scoring.reason_codes or [])],
                )
            output = SalesStrategyAgentOutput(
                approach=approach,
                objection_key=objection_key,
                next_best_action=next_best_action,
                tone="empathetic" if objection_key or intent_data.get("is_support") else "professional",
                key_points=key_points,
                scoring=scoring_summary,
                strategy=strategy,
                objective=objective,
                persuasive_angle=persuasive_angle,
                recommended_cta=recommended_cta,
            )
            context.sales_strategy_output = output.to_dict()
            context.routing_output = routing
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "approach": approach,
                    "objection_key": objection_key,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
