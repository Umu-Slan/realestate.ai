"""
Buyer journey stage detection - from current message + prior history.
Determines where the lead/customer is in the journey for next-best-action logic.
"""
from core.enums import BuyerJourneyStage


def detect_journey_stage(
    *,
    intent_primary: str = "",
    customer_type: str = "",
    temperature: str = "",
    score: int = 0,
    qualification: dict | None = None,
    routing_route: str = "",
    prior_stage: str = "",
    has_project_preference: bool = False,
    has_budget: bool = False,
    has_location: bool = False,
) -> str:
    """
    Detect journey stage from current context.
    Returns stage value (e.g. awareness, consideration, shortlisting).
    """
    intent = (intent_primary or "").lower()
    route = (routing_route or "").lower()
    qual = qualification or {}

    # Support path -> support_retention
    if customer_type in ("support_customer", "existing_customer"):
        if route in ("support", "support_escalation", "legal_handoff"):
            return BuyerJourneyStage.SUPPORT_RETENTION.value
        if any(x in intent for x in ("complaint", "installment", "contract", "maintenance", "delivery", "documentation", "payment")):
            return BuyerJourneyStage.SUPPORT_RETENTION.value

    # Post-purchase intents -> post_booking
    if any(x in intent for x in ("installment", "delivery", "handover", "documentation", "payment_proof")):
        return BuyerJourneyStage.POST_BOOKING.value

    # Visit/schedule intent + qualified -> visit_planning
    if "visit" in intent or "schedule" in intent or "زيارة" in intent:
        if has_budget or has_location or has_project_preference:
            return BuyerJourneyStage.VISIT_PLANNING.value
        return BuyerJourneyStage.CONSIDERATION.value

    # Brochure request + some qualification -> shortlisting
    if "brochure" in intent and (has_project_preference or has_budget or has_location):
        return BuyerJourneyStage.SHORTLISTING.value

    # Project/price inquiry with budget+location -> shortlisting
    if ("project" in intent or "price" in intent) and has_budget and has_location:
        return BuyerJourneyStage.SHORTLISTING.value

    # Project/price inquiry with some qualification -> consideration
    if ("project" in intent or "price" in intent) and (has_budget or has_location or has_project_preference):
        return BuyerJourneyStage.CONSIDERATION.value

    # Hot lead with visit interest -> visit_planning or negotiation
    if temperature == "hot" and score >= 75:
        return BuyerJourneyStage.VISIT_PLANNING.value

    # Warm with project preference -> shortlisting
    if temperature == "warm" and has_project_preference:
        return BuyerJourneyStage.SHORTLISTING.value

    # Warm with budget -> consideration
    if temperature == "warm" and has_budget:
        return BuyerJourneyStage.CONSIDERATION.value

    # Cold/nurture with any qualification -> consideration
    if temperature in ("cold", "nurture") and (has_budget or has_location):
        return BuyerJourneyStage.CONSIDERATION.value

    # Generic project/price/location inquiry -> awareness
    if any(x in intent for x in ("project", "price", "location", "property", "شقة", "مشروع")):
        return BuyerJourneyStage.AWARENESS.value

    # Prior stage fallback
    if prior_stage and prior_stage in [s[0] for s in BuyerJourneyStage.choices]:
        return prior_stage

    # Temperature-based fallback
    if temperature == "hot":
        return BuyerJourneyStage.VISIT_PLANNING.value
    if temperature == "warm":
        return BuyerJourneyStage.CONSIDERATION.value
    if temperature in ("cold", "nurture"):
        return BuyerJourneyStage.AWARENESS.value

    return BuyerJourneyStage.UNKNOWN.value
