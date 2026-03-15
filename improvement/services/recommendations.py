"""
Generate offline operator recommendations from improvement signals.
Reviewable suggestions only - no automatic production changes.
"""
from typing import Optional

from improvement.models import ImprovementSignal


def generate_operator_recommendations(
    *,
    company_id: Optional[int] = None,
    limit: int = 50,
    issue_types: Optional[list[str]] = None,
) -> list[dict]:
    """
    Build operator-facing recommendation list from ImprovementSignals.
    Each item includes: issue_type, pattern_key, frequency, recommended_action, example_refs.
    """
    qs = ImprovementSignal.objects.filter(
        review_status="pending",
        frequency__gte=1,
    ).order_by("-frequency", "-last_seen_at")
    if company_id:
        qs = qs.filter(company_id=company_id)
    else:
        qs = qs.filter(company__isnull=True)
    if issue_types:
        qs = qs.filter(issue_type__in=issue_types)
    signals = list(qs[:limit])
    out = []
    for s in signals:
        action = s.recommended_action or _default_recommendation(s)
        out.append({
            "id": s.id,
            "issue_type": s.issue_type,
            "source_feature": s.source_feature,
            "pattern_key": s.pattern_key,
            "frequency": s.frequency,
            "affected_mode": s.affected_mode,
            "affected_intent": s.affected_intent,
            "recommended_action": action,
            "example_refs": s.example_refs or [],
            "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else "",
        })
    return out


def _default_recommendation(signal: ImprovementSignal) -> str:
    """Fallback recommended_action based on issue_type."""
    mapping = {
        "corrected_response": "Review corrected responses; add more FAQ knowledge about this topic",
        "escalation_reason": "Add more FAQ knowledge or tighten guardrail for this escalation trigger",
        "support_category": "Support category confusion; review triage rules",
        "objection_type": "Improve objection handling; add objection library content",
        "low_confidence": "Improve classification or add clarification prompts",
        "failed_recommendation": "Recommendation weak spot; review match criteria or add FAQ knowledge",
        "missing_qualification": "Improve qualification logic; add extraction prompts or fallback questions",
        "score_routing_disagreement": "Sales scoring rule may need adjustment; review routing logic",
        "repeated_fallback_reply": "Improve knowledge in area X; add qualification prompts",
        "low_confidence_recommendation": "Improve matching or qualification; add project knowledge",
        "objection_handling_failure": "Improve objection handling for this concern",
        "weak_stage_advancement": "Improve stage advancement; strengthen CTAs",
        "cold_to_hot_opportunity": "Tighten strategy for conversion; propose visit earlier",
        "high_value_escaped_late": "Consider earlier move_to_human for hot leads",
    }
    return mapping.get(signal.issue_type, "Review this pattern and consider system improvement")
