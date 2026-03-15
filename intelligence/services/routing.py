"""
Business routing rules - deterministic.
"""
from core.enums import SupportCategory, IntentCategory
from intelligence.schemas import (
    IntentResult,
    QualificationExtraction,
    ScoringResult,
    RoutingDecision,
    ConversationIntelligenceResult,
)


def apply_routing_rules(
    intent: IntentResult,
    qualification: QualificationExtraction,
    scoring: ScoringResult,
    customer_type: str,
    is_angry: bool = False,
    exact_price_available: bool = True,
) -> RoutingDecision:
    """
    Deterministic routing based on business rules.
    """
    route = "sales"
    queue = ""
    priority = "normal"
    requires_human_review = False
    safe_response_policy = False
    escalation_ready = False
    quarantine = False
    handoff_type = ""
    reason = ""

    primary = (intent.primary or "").lower()

    # Spam -> quarantine
    if intent.is_spam or primary == IntentCategory.SPAM:
        return RoutingDecision(
            route="quarantine",
            quarantine=True,
            handoff_type="",
            reason="Spam likelihood high",
        )

    # Angry existing customer -> escalation-ready support
    if is_angry and customer_type in ("existing_customer", "support_customer"):
        return RoutingDecision(
            route="support_escalation",
            queue="urgent_support",
            priority="high",
            escalation_ready=True,
            handoff_type="support",
            reason="Angry existing customer",
        )

    # Legal/contract -> support/legal handoff only
    if primary in (IntentCategory.CONTRACT_ISSUE,):
        return RoutingDecision(
            route="legal_handoff",
            queue="legal_review",
            handoff_type="legal",
            reason="Contract/legal issue",
        )

    # Exact price unavailable -> safe response
    if not exact_price_available and primary == IntentCategory.PRICE_INQUIRY:
        return RoutingDecision(
            route="sales",
            safe_response_policy=True,
            handoff_type="sales",
            reason="Exact price unavailable - use safe response policy",
        )

    # Score >= 80 and visit requested -> senior sales
    if scoring.score >= 80 and primary == IntentCategory.SCHEDULE_VISIT:
        return RoutingDecision(
            route="senior_sales",
            queue="senior_sales",
            priority="high",
            handoff_type="sales",
            reason="Hot lead requesting visit",
        )

    # Low confidence -> clarification or human review
    if scoring.confidence == "low":
        return RoutingDecision(
            route="clarification",
            requires_human_review=True,
            handoff_type="clarification",
            reason="Low confidence - clarification or human review",
        )

    # Support intents -> support route
    if intent.is_support or customer_type == "support_customer":
        route = "support"
        queue = "support"
        handoff_type = "support"

    # Broker -> broker queue
    if intent.is_broker or primary == IntentCategory.BROKER_INQUIRY:
        route = "broker"
        queue = "broker_sales"
        handoff_type = "sales"

    return RoutingDecision(
        route=route,
        queue=queue or "default",
        priority=priority,
        requires_human_review=requires_human_review,
        safe_response_policy=safe_response_policy,
        escalation_ready=escalation_ready,
        quarantine=quarantine,
        handoff_type=handoff_type or "sales",
        reason=reason or "Default routing",
    )


def classify_support_category(intent: IntentResult) -> str:
    """Map intent to support category for existing customers."""
    primary = (intent.primary or "").lower()
    mapping = {
        IntentCategory.INSTALLMENT_INQUIRY: SupportCategory.INSTALLMENT,
        IntentCategory.CONTRACT_ISSUE: SupportCategory.CONTRACT,
        IntentCategory.MAINTENANCE_ISSUE: SupportCategory.MAINTENANCE,
        IntentCategory.DELIVERY_INQUIRY: SupportCategory.HANDOVER,
        IntentCategory.DOCUMENTATION_INQUIRY: SupportCategory.DOCUMENTATION,
        IntentCategory.PAYMENT_PROOF_INQUIRY: SupportCategory.PAYMENT_PROOF,
        IntentCategory.SUPPORT_COMPLAINT: SupportCategory.COMPLAINT,
        IntentCategory.GENERAL_SUPPORT: SupportCategory.GENERAL_SUPPORT,
    }
    val = mapping.get(primary, SupportCategory.GENERAL_SUPPORT)
    return val.value if hasattr(val, "value") else val
