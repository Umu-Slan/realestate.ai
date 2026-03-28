"""
Next best action logic - deterministic, explainable.
"""
from dataclasses import dataclass
from enum import Enum


class NextBestAction(str, Enum):
    """Available next actions - aligned with buyer journey stages."""
    ASK_BUDGET = "ask_budget"
    ASK_PREFERRED_AREA = "ask_preferred_area"
    SEND_BROCHURE = "send_brochure"
    RECOMMEND_PROJECT = "recommend_project"
    PROPOSE_VISIT = "propose_visit"
    REQUEST_SCHEDULING = "request_scheduling"  # Alias for propose_visit
    ASSIGN_SALES_REP = "assign_sales_rep"
    CREATE_SUPPORT_CASE = "create_support_case"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    NURTURE_CONTENT = "nurture_content"
    CLARIFY_INTENT = "clarify_intent"
    NONE = "none"


@dataclass
class NextActionResult:
    """Next best action with explanation."""
    action: NextBestAction
    reason: str
    priority: int = 0  # higher = more urgent


def compute_next_best_action(
    *,
    customer_type: str = "",
    intent_primary: str = "",
    missing_fields: list | None = None,
    score: int = 0,
    temperature: str = "",
    routing: dict | None = None,
    requires_clarification: bool = False,
    journey_stage: str = "",
) -> NextActionResult:
    """
    Deterministic next best action based on context.
    """
    missing = missing_fields or []
    routing = routing or {}
    intent = (intent_primary or "").lower()
    stage = (journey_stage or "").lower()

    # Escalation path
    if routing.get("escalation_ready") or routing.get("force_escalation"):
        return NextActionResult(
            action=NextBestAction.ESCALATE_TO_HUMAN,
            reason="Escalation required",
            priority=100,
        )
    if requires_clarification:
        return NextActionResult(
            action=NextBestAction.CLARIFY_INTENT,
            reason="Low confidence - need clarification",
            priority=80,
        )

    # Support path
    if customer_type in ("support_customer", "existing_customer"):
        if "support" in intent or routing.get("handoff_type") == "support":
            return NextActionResult(
                action=NextBestAction.CREATE_SUPPORT_CASE,
                reason="Support inquiry - create case",
                priority=90,
            )
        if routing.get("handoff_type") == "legal":
            return NextActionResult(
                action=NextBestAction.ESCALATE_TO_HUMAN,
                reason="Legal handoff",
                priority=95,
            )

    # Lead path - prioritize by missing qualification
    if "budget" in missing and temperature in ("cold", "nurture", "warm"):
        return NextActionResult(
            action=NextBestAction.ASK_BUDGET,
            reason="Budget not specified",
            priority=50,
        )
    if "location" in missing and temperature in ("cold", "nurture"):
        return NextActionResult(
            action=NextBestAction.ASK_PREFERRED_AREA,
            reason="Location preference missing",
            priority=45,
        )

    # Hot lead in visit_planning -> assign sales rep
    if stage == "visit_planning" and temperature == "hot" and score >= 75:
        return NextActionResult(
            action=NextBestAction.ASSIGN_SALES_REP,
            reason="Hot lead ready for visit - assign rep",
            priority=88,
        )

    # Intent-specific (before "fully qualified" shortcut — empty missing_fields is not the same as qualified)
    if "brochure" in intent or intent == "brochure_request":
        return NextActionResult(
            action=NextBestAction.SEND_BROCHURE,
            reason="Brochure requested",
            priority=70,
        )
    if "visit" in intent or "schedule" in intent:
        return NextActionResult(
            action=NextBestAction.PROPOSE_VISIT,
            reason="Visit/schedule interest",
            priority=85,
        )
    if "project" in intent or "price" in intent:
        return NextActionResult(
            action=NextBestAction.RECOMMEND_PROJECT,
            reason="Project/price inquiry",
            priority=60,
        )

    # Budget + location no longer missing -> suggest matching projects
    if missing and "budget" not in missing and "location" not in missing:
        return NextActionResult(
            action=NextBestAction.RECOMMEND_PROJECT,
            reason="Qualified - suggest matching projects",
            priority=65,
        )

    # Temperature-based
    if temperature == "hot":
        return NextActionResult(
            action=NextBestAction.PROPOSE_VISIT,
            reason="Hot lead - propose visit",
            priority=75,
        )
    if temperature == "warm":
        return NextActionResult(
            action=NextBestAction.SEND_BROCHURE,
            reason="Warm lead - send materials",
            priority=55,
        )
    if temperature in ("cold", "nurture"):
        return NextActionResult(
            action=NextBestAction.NURTURE_CONTENT,
            reason="Nurture with content",
            priority=30,
        )

    return NextActionResult(
        action=NextBestAction.CLARIFY_INTENT,
        reason="Default - clarify needs",
        priority=20,
    )
