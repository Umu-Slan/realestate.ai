"""
Reinforcement signals - record outcome signals for improvement insights.
Structured records linked to conversation, customer, recommendation, stage, strategy.
"""
from typing import Optional, Any

from improvement.models import ReinforcementSignal, REINFORCEMENT_SIGNAL_TYPES


VALID_SIGNAL_TYPES = frozenset(t[0] for t in REINFORCEMENT_SIGNAL_TYPES)


def record_reinforcement_signal(
    signal_type: str,
    *,
    conversation_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    recommendation_id: Optional[int] = None,
    message_id: Optional[int] = None,
    journey_stage: str = "",
    strategy: str = "",
    intent_primary: str = "",
    metadata: Optional[dict] = None,
    company_id: Optional[int] = None,
) -> Optional[ReinforcementSignal]:
    """
    Record a reinforcement outcome signal.
    Returns the created ReinforcementSignal or None on validation error.
    """
    if signal_type not in VALID_SIGNAL_TYPES:
        return None

    try:
        return ReinforcementSignal.objects.create(
            company_id=company_id,
            signal_type=signal_type,
            conversation_id=conversation_id,
            customer_id=customer_id,
            recommendation_id=recommendation_id,
            message_id=message_id,
            journey_stage=(journey_stage or "")[:64],
            strategy=(strategy or "")[:64],
            intent_primary=(intent_primary or "")[:64],
            metadata=dict(metadata or {}),
        )
    except Exception:
        return None


def get_reinforcement_signals_for_insights(
    *,
    days: int = 30,
    signal_types: Optional[list[str]] = None,
    company_id: Optional[int] = None,
):
    """
    Query reinforcement signals for Improvement Insights aggregation.
    Returns queryset filtered by period and optional signal types.
    """
    from datetime import timedelta
    from django.utils import timezone

    since = timezone.now() - timedelta(days=days)
    qs = ReinforcementSignal.objects.filter(created_at__gte=since)
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    if signal_types:
        qs = qs.filter(signal_type__in=signal_types)
    return qs.order_by("-created_at")
