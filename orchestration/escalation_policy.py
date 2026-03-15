"""
Enterprise-grade escalation policy - maps triggers to EscalationReason.
Single source of truth for when and why escalations are created.
"""
from core.enums import EscalationReason


def resolve_escalation_reason(
    *,
    is_angry: bool = False,
    intent_primary: str = "",
    routing_route: str = "",
    routing_safe_response_policy: bool = False,
    routing_requires_human_review: bool = False,
    policy_forced_escalation: bool = False,
    policy_violations: list | None = None,
    has_verified_pricing: bool = True,
    intent_is_price_inquiry: bool = False,
    is_vip: bool = False,
    escalation_flags: list | None = None,
) -> EscalationReason:
    """
    Map escalation triggers to canonical EscalationReason.
    Priority: most specific trigger wins.
    """
    intent = (intent_primary or "").lower()
    route = (routing_route or "").lower()
    flags = escalation_flags or []
    violations = policy_violations or []

    # Angry customer -> ANGRY_CUSTOMER
    if is_angry:
        return EscalationReason.ANGRY_CUSTOMER

    # Legal/contract intent or route -> LEGAL_CONTRACT
    if "contract" in intent or "عقد" in intent or route == "legal_handoff":
        return EscalationReason.LEGAL_CONTRACT

    # Severe complaint (angry + complaint already handled above; complaint alone)
    if "complaint" in intent or "شكوى" in intent:
        return EscalationReason.SEVERE_COMPLAINT

    # Pricing exception: price inquiry but unavailable verified pricing
    if intent_is_price_inquiry and not has_verified_pricing:
        return EscalationReason.PRICING_EXCEPTION

    # Unavailable critical info: safe_response_policy (exact price/availability unavailable)
    if routing_safe_response_policy:
        return EscalationReason.UNAVAILABLE_CRITICAL_INFO

    # Policy forced (guardrail violations, legal advice block)
    if policy_forced_escalation or "policy_forced_escalation" in flags:
        if any("legal" in str(v).lower() for v in violations):
            return EscalationReason.LEGAL_CONTRACT
        if any("price" in str(v).lower() or "unverified" in str(v).lower() for v in violations):
            return EscalationReason.PRICING_EXCEPTION
        return EscalationReason.NEGOTIATION_BEYOND_POLICY

    # Low confidence -> requires human review
    if routing_requires_human_review:
        return EscalationReason.LOW_CONFIDENCE

    # VIP lead
    if is_vip or "vip" in route:
        return EscalationReason.VIP_LEAD

    # Default: complex inquiry
    return EscalationReason.COMPLEX_INQUIRY
