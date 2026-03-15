"""
Conversation intelligence pipeline - full analysis on incoming message.
"""
from typing import Sequence

from core.enums import CustomerType
from intelligence.schemas import (
    ConversationIntelligenceResult,
    IntentResult,
    QualificationExtraction,
    ScoringResult,
    RoutingDecision,
)
from intelligence.services.intent_classifier import classify_intent
from intelligence.services.qualification_extractor import extract_qualification
from intelligence.services.scoring_engine import score_lead
from intelligence.services.routing import apply_routing_rules, classify_support_category


def analyze_message(
    message_text: str,
    *,
    conversation_history: Sequence[dict] | None = None,
    customer_id: int | None = None,
    customer_type: str = "",
    is_existing_customer: bool = False,
    is_returning_lead: bool = False,
    message_count: int = 1,
    has_project_match: bool = False,
    decision_authority_signals: bool = False,
    is_angry: bool = False,
    exact_price_available: bool = True,
    use_llm: bool = True,
    source_channel: str = "",
) -> ConversationIntelligenceResult:
    """
    Full pipeline: who is user, what they want, score, route.
    """
    history = list(conversation_history or [])

    # 1. Intent
    intent = classify_intent(
        message_text,
        conversation_history=history,
        customer_type=customer_type,
        use_llm=use_llm,
    )

    # 2. Resolve customer type if not provided
    if not customer_type:
        if intent.is_spam:
            customer_type = CustomerType.SPAM
        elif intent.is_broker:
            customer_type = CustomerType.BROKER
        elif intent.is_support or intent.primary in [
            "support_complaint", "contract_issue", "maintenance_issue",
            "delivery_inquiry", "general_support", "documentation_inquiry",
            "payment_proof_inquiry", "installment_inquiry",
        ]:
            customer_type = CustomerType.SUPPORT_CUSTOMER
        elif is_returning_lead:
            customer_type = CustomerType.RETURNING_LEAD
        elif is_existing_customer:
            customer_type = CustomerType.EXISTING_CUSTOMER
        else:
            customer_type = CustomerType.NEW_LEAD

    # Normalize to value if enum passed
    if hasattr(customer_type, "value"):
        customer_type = customer_type.value

    # 3. Qualification (for leads, not spam)
    qualification = QualificationExtraction(confidence="unknown", missing_fields=[])
    if not intent.is_spam and customer_type not in (CustomerType.SPAM.value, "spam"):
        qualification = extract_qualification(
            message_text,
            conversation_history=history,
            use_llm=use_llm,
        )
        # Contradictory qualification: budget_min > budget_max
        from core.resilience import detect_contradictory_qualification
        if detect_contradictory_qualification(qualification.budget_min, qualification.budget_max):
            qualification.confidence = "low"
            qualification.missing_fields = (qualification.missing_fields or []) + ["budget_clarity"]

    # 4. Scoring (for leads)
    scoring = ScoringResult(
        score=0,
        temperature="nurture",
        confidence="unknown",
        reason_codes=[],
        missing_fields=[],
        next_best_action="",
        recommended_route="nurture",
    )
    # Resolve source_channel from customer if not provided
    if not source_channel and customer_id:
        try:
            from leads.models import Customer
            cust = Customer.objects.filter(pk=customer_id).first()
            if cust:
                source_channel = getattr(cust.source_channel, "value", str(cust.source_channel))
        except Exception:
            pass

    lead_types = (CustomerType.NEW_LEAD.value, CustomerType.RETURNING_LEAD.value, CustomerType.BROKER.value, "new_lead", "returning_lead", "broker")
    if customer_type in lead_types:
        scoring = score_lead(
            qualification,
            intent,
            is_returning=is_returning_lead,
            message_count=message_count,
            has_project_match=has_project_match,
            decision_authority_signals=decision_authority_signals,
            source_channel=source_channel,
        )

    # 5. Routing
    routing = apply_routing_rules(
        intent=intent,
        qualification=qualification,
        scoring=scoring,
        customer_type=customer_type,
        is_angry=is_angry,
        exact_price_available=exact_price_available,
    )

    # 6. Support category (for existing customers)
    support_category = ""
    if customer_type in (CustomerType.EXISTING_CUSTOMER.value, CustomerType.SUPPORT_CUSTOMER.value, "existing_customer", "support_customer"):
        support_category = classify_support_category(intent)
        if hasattr(support_category, "value"):
            support_category = support_category.value

    # 7. Ambiguity / clarification
    is_ambiguous = (
        intent.confidence < 0.5 or
        (qualification.confidence == "low" and len(qualification.missing_fields or []) > 4)
    )
    requires_clarification = routing.requires_human_review or (
        scoring.confidence == "low" and customer_type in (CustomerType.NEW_LEAD.value, "new_lead")
    )

    return ConversationIntelligenceResult(
        customer_type=customer_type,
        intent=intent,
        qualification=qualification,
        scoring=scoring,
        routing=routing,
        support_category=support_category,
        is_ambiguous=is_ambiguous,
        requires_clarification=requires_clarification,
    )
