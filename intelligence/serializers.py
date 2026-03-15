"""
Serialize intelligence results to API-friendly dicts.
"""
from decimal import Decimal

from intelligence.schemas import (
    ConversationIntelligenceResult,
    IntentResult,
    QualificationExtraction,
    ScoringResult,
    ReasonCode,
    RoutingDecision,
)


def _serialize_reason(r: ReasonCode) -> dict:
    return {"factor": r.factor, "contribution": r.contribution, "note": r.note}


def serialize_intelligence(result: ConversationIntelligenceResult) -> dict:
    """Convert full pipeline result to JSON-serializable dict."""
    def _decimal_to_val(v):
        return float(v) if isinstance(v, Decimal) else v

    qual = result.qualification
    qual_dict = {
        "budget_min": _decimal_to_val(qual.budget_min),
        "budget_max": _decimal_to_val(qual.budget_max),
        "budget_clarity": qual.budget_clarity,
        "location_preference": qual.location_preference,
        "project_preference": qual.project_preference,
        "property_type": qual.property_type,
        "residence_vs_investment": qual.residence_vs_investment,
        "payment_method": qual.payment_method,
        "purchase_timeline": qual.purchase_timeline,
        "financing_readiness": qual.financing_readiness,
        "family_size": qual.family_size,
        "urgency": qual.urgency,
        "missing_fields": qual.missing_fields or [],
        "confidence": qual.confidence,
    }

    intent = result.intent
    intent_dict = {
        "primary": intent.primary,
        "secondary": intent.secondary or [],
        "confidence": intent.confidence,
        "is_support": intent.is_support,
        "is_spam": intent.is_spam,
        "is_broker": intent.is_broker,
    }

    scoring = result.scoring
    scoring_dict = {
        "score": scoring.score,
        "temperature": scoring.temperature,
        "confidence": scoring.confidence,
        "reason_codes": [_serialize_reason(r) for r in (scoring.reason_codes or [])],
        "missing_fields": scoring.missing_fields or [],
        "next_best_action": scoring.next_best_action,
        "recommended_route": scoring.recommended_route,
    }

    routing = result.routing
    routing_dict = {
        "route": routing.route,
        "queue": routing.queue,
        "priority": routing.priority,
        "requires_human_review": routing.requires_human_review,
        "safe_response_policy": routing.safe_response_policy,
        "escalation_ready": routing.escalation_ready,
        "quarantine": routing.quarantine,
        "handoff_type": routing.handoff_type,
        "reason": routing.reason,
    }

    return {
        "customer_type": result.customer_type,
        "intent": intent_dict,
        "qualification": qual_dict,
        "scoring": scoring_dict,
        "routing": routing_dict,
        "support_category": result.support_category,
        "is_ambiguous": result.is_ambiguous,
        "requires_clarification": result.requires_clarification,
    }
