"""
Multi-agent sales improvement insights.
Aggregates patterns: fallback replies, missing qualification, low-confidence recommendations,
objection failures, weak stage advancement, cold-to-hot opportunities, high-value escaped late.
"""
from collections import Counter
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from console.models import OrchestrationSnapshot
from improvement.models import ImprovementSignal
from support.models import Escalation


# Known fallback / generic opener phrases (Arabic + English)
FALLBACK_PHRASES = frozenset({
    "مرحباً! كيف يمكنني مساعدتك؟",
    "أهلاً وسهلاً! كيف يمكنني مساعدتك؟",
    "أهلاً! سعيد بتواصلك.",
    "Hello! How can I help you?",
    "Hi! How can I help?",
    "مرحباً",
    "أهلاً",
})


def _upsert_signal(
    *,
    issue_type: str,
    source_feature: str,
    pattern_key: str,
    frequency: int,
    affected_mode: str = "",
    affected_intent: str = "",
    example_refs: list,
    recommended_action: str,
    company_id: Optional[int] = None,
) -> ImprovementSignal:
    """Create or update improvement signal."""
    qs = ImprovementSignal.objects.filter(
        issue_type=issue_type,
        pattern_key=pattern_key,
        affected_mode=affected_mode or "",
        affected_intent=affected_intent or "",
    )
    if company_id:
        qs = qs.filter(company_id=company_id)
    else:
        qs = qs.filter(company__isnull=True)
    signal = qs.first()
    if signal:
        signal.frequency += frequency
        signal.example_refs = (signal.example_refs or []) + example_refs
        signal.example_refs = signal.example_refs[-20:]
        signal.last_seen_at = timezone.now()
        if recommended_action and not signal.recommended_action:
            signal.recommended_action = recommended_action
        signal.save()
        return signal
    return ImprovementSignal.objects.create(
        company_id=company_id,
        issue_type=issue_type,
        source_feature=source_feature,
        pattern_key=pattern_key,
        frequency=frequency,
        affected_mode=affected_mode or "",
        affected_intent=affected_intent or "",
        example_refs=example_refs[:10],
        recommended_action=recommended_action,
    )


def aggregate_repeated_fallback_reply(days: int, company_id: Optional[int], sample_size: int = 2000) -> int:
    """Repeated generic/fallback replies - improve knowledge or qualification prompts."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(created_at__gte=since)[:sample_size]
    counter = Counter()
    refs_map = {}
    for s in snapshots:
        resp = (s.response_produced or "").strip()
        if len(resp) < 120 and (
            resp in FALLBACK_PHRASES
            or any(fp in resp for fp in FALLBACK_PHRASES)
            or (len(resp) < 50 and ("مرحباً" in resp or "أهلاً" in resp or "Hello" in resp or "Hi " in resp))
        ):
            key = "generic_opener"
            counter[key] += 1
            if key not in refs_map:
                refs_map[key] = []
            refs = [{"type": "snapshot", "id": s.id}]
            if s.conversation_id:
                refs.append({"type": "conversation", "id": s.conversation_id})
            refs_map[key] = refs_map[key] + refs
    count = 0
    for key, freq in counter.most_common(5):
        _upsert_signal(
            issue_type="repeated_fallback_reply",
            source_feature="sales",
            pattern_key=key,
            frequency=freq,
            example_refs=refs_map.get(key, [])[:10],
            recommended_action="Improve knowledge in area X; add qualification prompts or retrieval for common intents",
            company_id=company_id,
        )
        count += 1
    return count


def aggregate_low_confidence_recommendation(days: int, company_id: Optional[int], sample_size: int = 1500) -> int:
    """Low confidence in recommendations - improve matching or qualification."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(
        created_at__gte=since,
        mode="sales",
    )[:sample_size]
    count = 0
    for s in snapshots:
        qual = s.qualification or {}
        scoring = s.scoring or {}
        conf = scoring.get("confidence")
        if isinstance(conf, (int, float)) and conf < 0.6:
            pass  # numeric low
        elif conf in ("low", "unknown", ""):
            pass  # string low
        else:
            continue
        primary = (s.intent or {}).get("primary", "unknown") if isinstance(s.intent, dict) else "unknown"
        refs = [{"type": "snapshot", "id": s.id}]
        if s.conversation_id:
            refs.append({"type": "conversation", "id": s.conversation_id})
        pattern = primary or "general"
        _upsert_signal(
            issue_type="low_confidence_recommendation",
            source_feature="recommendation",
            pattern_key=pattern,
            frequency=1,
            affected_mode=s.mode or "",
            affected_intent=primary,
            example_refs=refs,
            recommended_action="Improve matching or qualification; add more project knowledge for intent",
            company_id=company_id,
        )
        count += 1
    return count


def aggregate_objection_handling_failure(days: int, company_id: Optional[int]) -> int:
    """Objection handling failures - improve objection library for specific concerns."""
    try:
        from improvement.services.reinforcement_signals import get_reinforcement_signals_for_insights
        qs = get_reinforcement_signals_for_insights(
            days=days,
            company_id=company_id,
            signal_types=["objection_unresolved"],
        )[:500]
    except Exception:
        return 0
    counter = Counter()
    refs_map = {}
    for rs in qs:
        obj_key = (rs.metadata or {}).get("objection_key", "unknown")
        pattern = obj_key or "general"
        counter[pattern] += 1
        if pattern not in refs_map:
            refs_map[pattern] = []
        refs = [{"type": "reinforcement_signal", "id": rs.id}]
        if rs.conversation_id:
            refs.append({"type": "conversation", "id": rs.conversation_id})
        refs_map[pattern] = refs_map[pattern] + refs
    count = 0
    rec_map = {
        "price_too_high": "Improve objection handling for price concerns; add value framing",
        "location_concern": "Improve objection handling for location/area concerns",
        "comparing_projects": "Improve objection handling when comparing projects",
        "payment_plan_mismatch": "Improve objection handling for financing/payment concerns",
        "delivery_concerns": "Improve objection handling for delivery timeline",
    }
    for pattern, freq in counter.most_common(10):
        action = rec_map.get(pattern, f"Improve objection handling for {pattern}")
        _upsert_signal(
            issue_type="objection_handling_failure",
            source_feature="sales",
            pattern_key=pattern,
            frequency=freq,
            example_refs=refs_map.get(pattern, [])[:10],
            recommended_action=action,
            company_id=company_id,
        )
        count += 1
    return count


def aggregate_weak_stage_advancement(days: int, company_id: Optional[int], sample_size: int = 300) -> int:
    """Conversations stuck in same stage for 3+ turns - improve stage advancement."""
    since = timezone.now() - timedelta(days=days)
    snapshots = list(
        OrchestrationSnapshot.objects.filter(created_at__gte=since)
        .order_by("conversation_id", "created_at")
        .values("conversation_id", "journey_stage", "id", "created_at")[:sample_size * 3]
    )
    by_conv = {}
    for s in snapshots:
        cid = s.get("conversation_id")
        if not cid:
            continue
        if cid not in by_conv:
            by_conv[cid] = []
        by_conv[cid].append(s)
    count = 0
    for cid, snaps in by_conv.items():
        if len(snaps) < 3:
            continue
        stages = [x.get("journey_stage") or "unknown" for x in snaps]
        same = all(st == stages[0] for st in stages)
        if same and stages[0] not in ("unknown", ""):
            refs = [{"type": "conversation", "id": cid}, {"type": "snapshot", "id": snaps[-1].get("id")}]
            _upsert_signal(
                issue_type="weak_stage_advancement",
                source_feature="sales",
                pattern_key=stages[0],
                frequency=1,
                example_refs=refs,
                recommended_action="Improve stage advancement; strengthen CTAs to move from this stage",
                company_id=company_id,
            )
            count += 1
    return count


def aggregate_cold_to_hot_opportunity(days: int, company_id: Optional[int], sample_size: int = 1500) -> int:
    """Cold/nurture leads with visit/purchase intent - tighten conversion strategy."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(
        created_at__gte=since,
        mode="sales",
    )[:sample_size]
    count = 0
    for s in snapshots:
        scoring = s.scoring or {}
        intent = s.intent or {}
        temp = (scoring.get("temperature") or "").lower()
        primary = (intent.get("primary") or "").lower() if isinstance(intent, dict) else ""
        if temp not in ("cold", "nurture", "unqualified"):
            continue
        if not any(x in primary for x in ("visit", "schedule", "booking", "purchase", "معاينة", "حجز")):
            continue
        refs = [{"type": "snapshot", "id": s.id}]
        if s.conversation_id:
            refs.append({"type": "conversation", "id": s.conversation_id})
        _upsert_signal(
            issue_type="cold_to_hot_opportunity",
            source_feature="sales",
            pattern_key=f"{temp}_{primary or 'intent'}",
            frequency=1,
            affected_intent=primary,
            example_refs=refs,
            recommended_action="Tighten strategy for investment/visit leads; propose visit CTA earlier",
            company_id=company_id,
        )
        count += 1
    return count


def aggregate_high_value_escaped_late(days: int, company_id: Optional[int]) -> int:
    """High-score leads that escalated - improve timely handoff."""
    since = timezone.now() - timedelta(days=days)
    escalations = Escalation.objects.filter(created_at__gte=since).select_related("conversation")
    from console.models import OrchestrationSnapshot
    count = 0
    for esc in escalations[:500]:
        cid = esc.conversation_id
        if not cid:
            continue
        snap = (
            OrchestrationSnapshot.objects.filter(conversation_id=cid)
            .order_by("-created_at")
            .first()
        )
        if not snap:
            continue
        scoring = snap.scoring or {}
        score = int(scoring.get("score") or 0)
        if score < 70:
            continue
        refs = [{"type": "escalation", "id": esc.id}, {"type": "conversation", "id": cid}]
        _upsert_signal(
            issue_type="high_value_escaped_late",
            source_feature="sales",
            pattern_key=f"score_{score}",
            frequency=1,
            example_refs=refs,
            recommended_action="High-value leads escalated late; consider earlier move_to_human for hot leads",
            company_id=company_id,
        )
        count += 1
    return count


def aggregate_sales_agent_insights(
    *,
    days: int = 30,
    company_id: Optional[int] = None,
) -> dict:
    """
    Aggregate multi-agent sales improvement insights.
    Returns counts per pattern type.
    """
    return {
        "repeated_fallback_reply": aggregate_repeated_fallback_reply(days, company_id),
        "low_confidence_recommendation": aggregate_low_confidence_recommendation(days, company_id),
        "objection_handling_failure": aggregate_objection_handling_failure(days, company_id),
        "weak_stage_advancement": aggregate_weak_stage_advancement(days, company_id),
        "cold_to_hot_opportunity": aggregate_cold_to_hot_opportunity(days, company_id),
        "high_value_escaped_late": aggregate_high_value_escaped_late(days, company_id),
    }
