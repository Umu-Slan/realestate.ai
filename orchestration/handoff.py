"""
Handoff summary generation for human escalation.
Enterprise-grade: customer identity, conversation summary, intent, qualification,
score/temperature, support category, routing, risk flags, recommended next action.
"""
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from leads.models import Customer
    from conversations.models import Conversation


def build_handoff_summary(
    *,
    customer_type: str = "",
    intent: dict | None = None,
    qualification: dict | None = None,
    scoring: dict | None = None,
    routing: dict | None = None,
    next_action: dict | None = None,
    risk_notes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate handoff summary for human agent.
    """
    intent = intent or {}
    qualification = qualification or {}
    scoring = scoring or {}
    routing = routing or {}
    next_action = next_action or {}
    risk_notes = risk_notes or []

    # Build qualification summary
    qual_parts = []
    if qualification.get("budget_min") or qualification.get("budget_max"):
        qual_parts.append(f"Budget: {qualification.get('budget_min', '')}-{qualification.get('budget_max', '')} EGP")
    if qualification.get("location_preference"):
        qual_parts.append(f"Location: {qualification['location_preference']}")
    if qualification.get("project_preference"):
        qual_parts.append(f"Project: {qualification['project_preference']}")
    if qualification.get("property_type"):
        qual_parts.append(f"Type: {qualification['property_type']}")
    if qualification.get("purchase_timeline"):
        qual_parts.append(f"Timeline: {qualification['purchase_timeline']}")
    if qualification.get("urgency"):
        qual_parts.append(f"Urgency: {qualification['urgency']}")
    qual_summary = "; ".join(qual_parts) if qual_parts else "No qualification yet"

    # Intent summary
    primary = intent.get("primary", "")
    secondary = intent.get("secondary", []) or []
    intent_summary = primary
    if secondary:
        intent_summary += f" (+ {', '.join(secondary[:3])})"

    # Score/category
    score_val = scoring.get("score", 0)
    temp = scoring.get("temperature", "")
    score_summary = f"Score: {score_val} ({temp})" if score_val is not None else "N/A"
    supp_cat = qualification.get("support_category", "")
    if supp_cat:
        score_summary += f" | Support: {supp_cat}"

    result: dict[str, Any] = {
        "customer_type": customer_type,
        "customer_identity": {},
        "conversation_summary": "",
        "intent_summary": intent_summary,
        "intent": {
            "primary": primary,
            "secondary": secondary,
            "summary": intent_summary,
        },
        "qualification_summary": qual_summary,
        "qualification": qualification,
        "score_and_category": score_summary,
        "scoring": {
            "score": scoring.get("score"),
            "temperature": scoring.get("temperature"),
            "reason_codes": scoring.get("reason_codes", [])[:5],
        },
        "support_category": qualification.get("support_category", ""),
        "routing": {
            "route": routing.get("route"),
            "queue": routing.get("queue"),
            "handoff_type": routing.get("handoff_type"),
            "escalation_ready": routing.get("escalation_ready"),
        },
        "risk_notes": risk_notes,
        "risk_flags": list(risk_notes),
        "recommended_next_step": next_action.get("reason", next_action.get("action", "")),
        "next_action": next_action,
    }
    return result


def enrich_handoff_with_identity(
    handoff_base: dict[str, Any],
    customer: "Customer | None",
    conversation: "Conversation | None",
) -> dict[str, Any]:
    """
    Enrich handoff summary with customer identity and conversation summary.
    Call from persistence when creating Escalation.
    """
    result = dict(handoff_base)
    result["customer_identity"] = _extract_customer_identity(customer)
    result["conversation_summary"] = _extract_conversation_summary(conversation)
    if conversation:
        result["conversation_id"] = conversation.id
    if customer:
        result["customer_id"] = customer.id
    return result


def _extract_customer_identity(customer: "Customer | None") -> dict[str, str]:
    if not customer or not getattr(customer, "identity", None):
        return {"name": "", "phone": "", "email": "", "external_id": ""}
    ident = customer.identity
    return {
        "name": getattr(ident, "name", "") or "",
        "phone": getattr(ident, "phone", "") or "",
        "email": getattr(ident, "email", "") or "",
        "external_id": getattr(ident, "external_id", "") or "",
    }


def _extract_conversation_summary(conversation: "Conversation | None", max_messages: int = 5) -> str:
    if not conversation:
        return ""
    try:
        messages = list(
            conversation.messages.order_by("-created_at")[:max_messages].values_list("role", "content", "created_at")
        )
        parts = []
        for role, content, created in reversed(messages):
            prefix = "User" if role == "user" else "Assistant"
            snip = (content or "")[:200] + ("..." if len(content or "") > 200 else "")
            parts.append(f"[{prefix}] {snip}")
        return " | ".join(parts) if parts else ""
    except Exception:
        return ""
