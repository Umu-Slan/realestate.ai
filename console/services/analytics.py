"""
Analytics service - real metrics from persisted data.
Operator and management dashboards.
"""
from collections import Counter
from datetime import timedelta
from django.db.models import Count, Avg
from django.utils import timezone

from leads.models import Customer, LeadScore
from conversations.models import Conversation, Message
from support.models import SupportCase, Escalation
from recommendations.models import Recommendation
from console.models import OrchestrationSnapshot
from core.enums import LeadTemperature, EscalationStatus
from engines.objection_library import detect_objection


def get_dashboard_metrics( *, days: int = 30) -> dict:
    """Core dashboard metrics from persisted data."""
    since = timezone.now() - timedelta(days=days)

    # Lead volume (customers who are leads, not just support)
    lead_types = ("new_lead", "returning_lead", "broker", "existing_customer")
    leads = Customer.objects.filter(
        is_active=True,
        customer_type__in=lead_types,
        created_at__gte=since,
    )
    lead_volume = leads.count()

    # Hot/warm/cold from LeadScore in period (score events by temperature)
    scores_since = LeadScore.objects.filter(created_at__gte=since)
    hot_count = scores_since.filter(temperature__in=(LeadTemperature.HOT.value, "hot")).count()
    warm_count = scores_since.filter(temperature__in=(LeadTemperature.WARM.value, "warm")).count()
    cold_count = scores_since.filter(temperature__in=(LeadTemperature.COLD.value, "cold", LeadTemperature.NURTURE.value, "nurture")).count()

    response_count = Message.objects.filter(role="assistant", created_at__gte=since).count()
    support_count = SupportCase.objects.filter(created_at__gte=since).count()
    escalation_open = Escalation.objects.filter(status=EscalationStatus.OPEN).count()
    escalation_total = Escalation.objects.filter(created_at__gte=since).count()
    recommendation_count = Recommendation.objects.filter(created_at__gte=since).count()

    # Channel distribution (Conversation.channel)
    channel_dist = list(
        Conversation.objects.filter(created_at__gte=since)
        .values("channel")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Sales conversion quality metrics
    total_scored = hot_count + warm_count + cold_count
    hot_lead_rate_pct = round(100 * hot_count / total_scored, 1) if total_scored > 0 else 0
    recommendation_rate_pct = round(100 * recommendation_count / response_count, 1) if response_count > 0 else 0
    top_objections = get_top_objections(limit=5, days=days)
    objection_count = sum(o["count"] for o in top_objections)

    return {
        "lead_volume": lead_volume,
        "hot_count": hot_count,
        "warm_count": warm_count,
        "cold_count": cold_count,
        "response_count": response_count,
        "support_cases": support_count,
        "escalations_open": escalation_open,
        "escalations_total": escalation_total,
        "recommendation_count": recommendation_count,
        "channel_distribution": channel_dist,
        "conversations": Conversation.objects.filter(created_at__gte=since).count(),
        "customers": Customer.objects.filter(is_active=True).count(),
        "days": days,
        # Sales conversion quality
        "hot_lead_rate_pct": hot_lead_rate_pct,
        "recommendation_rate_pct": recommendation_rate_pct,
        "objection_count": objection_count,
        "top_objections": top_objections,
        "total_leads_scored": total_scored,
    }


def get_top_intents(limit: int = 10, *, days: int = 30) -> list[dict]:
    """Top intents from OrchestrationSnapshot."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(created_at__gte=since)
    counter = Counter()
    for s in snapshots.iterator(chunk_size=500):
        primary = (s.intent or {}).get("primary") if isinstance(s.intent, dict) else None
        if primary:
            counter[primary] += 1
    return [{"intent": k, "count": v} for k, v in counter.most_common(limit)]


def get_top_support_categories(limit: int = 10, *, days: int = 30) -> list[dict]:
    """Top support categories."""
    since = timezone.now() - timedelta(days=days)
    return list(
        SupportCase.objects.filter(created_at__gte=since)
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


OBJECTION_LABELS: dict[str, str] = {
    "price_too_high": "Price",
    "location_concern": "Location",
    "trust_credibility": "Trust",
    "payment_plan_mismatch": "Payment plan",
    "investment_uncertainty": "Investment",
    "waiting_hesitation": "Hesitation",
    "comparing_projects": "Comparing",
    "delivery_concerns": "Delivery",
}


def get_top_objections(limit: int = 10, *, days: int = 30, sample_size: int = 500) -> list[dict]:
    """
    Top objections inferred from recent user messages.
    Runs detect_objection on sampled messages.
    """
    since = timezone.now() - timedelta(days=days)
    user_msgs = Message.objects.filter(
        role="user",
        created_at__gte=since,
    ).values_list("content", flat=True)[:sample_size]
    counter = Counter()
    for content in user_msgs:
        key = detect_objection(content)
        if key:
            counter[key] += 1
    return [
        {"objection": k, "label": OBJECTION_LABELS.get(k, k.replace("_", " ").title()), "count": v}
        for k, v in counter.most_common(limit)
    ]


def get_average_score_by_source(days: int = 30) -> list[dict]:
    """Average lead score by customer source_channel."""
    since = timezone.now() - timedelta(days=days)
    rows = list(
        LeadScore.objects.filter(created_at__gte=since)
        .values("customer__source_channel")
        .annotate(avg_score=Avg("score"), count=Count("id"))
        .order_by("-avg_score")
    )
    return [{"source": r["customer__source_channel"] or "unknown", "avg_score": round(r["avg_score"], 1), "count": r["count"]} for r in rows]


def get_escalation_reasons( *, days: int = 30) -> list[dict]:
    """Escalation count by reason."""
    since = timezone.now() - timedelta(days=days)
    return list(
        Escalation.objects.filter(created_at__gte=since)
        .values("reason")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
