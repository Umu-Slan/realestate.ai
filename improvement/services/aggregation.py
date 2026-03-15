"""
Aggregate improvement signals from persisted system behavior.
Read-only over domain data; writes only to ImprovementSignal.
Runs on demand (console refresh) - no automatic production changes.
"""
from collections import Counter
from datetime import timedelta
from typing import Optional

from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from improvement.models import ImprovementSignal
from improvement.services.reinforcement_signals import get_reinforcement_signals_for_insights
from improvement.services.sales_agent_insights import aggregate_sales_agent_insights
from audit.models import HumanCorrection
from console.models import ResponseFeedback
from support.models import Escalation, SupportCase
from recommendations.models import Recommendation
from leads.models import LeadQualification
from console.models import OrchestrationSnapshot
from conversations.models import Message
from engines.objection_library import detect_objection


QUALIFICATION_FIELDS = [
    ("budget_min", "budget_min", "Budget min"),
    ("budget_max", "budget_max", "Budget max"),
    ("property_type", "property_type", "Property type"),
    ("location_preference", "location_preference", "Location"),
    ("timeline", "timeline", "Timeline"),
]


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
    """Create or update improvement signal. Returns the signal."""
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


def _get_default_company_id() -> Optional[int]:
    try:
        from companies.services import get_default_company
        c = get_default_company()
        return c.id if c else None
    except Exception:
        return None


def _aggregate_corrected_responses(days: int, company_id: Optional[int]) -> int:
    """From HumanCorrection and ResponseFeedback (quality in weak/wrong or is_good=False).
    Uses sales linkage (strategy, objection_type, recommendation_quality, stage_decision) for pattern keys.
    """
    since = timezone.now() - timedelta(days=days)
    count = 0

    def _emit_pattern(pattern_key: str, source: str, rec: str, refs: list, mode: str = "", intent: str = ""):
        if not pattern_key:
            pattern_key = "general"
        _upsert_signal(
            issue_type="corrected_response",
            source_feature="orchestration",
            pattern_key=pattern_key,
            frequency=1,
            affected_mode=mode or "",
            affected_intent=intent or "",
            example_refs=refs,
            recommended_action=rec,
            company_id=company_id,
        )

    for hc in HumanCorrection.objects.filter(created_at__gte=since).select_related("message", "conversation"):
        it = hc.issue_type or hc.field_name or "unknown"
        if not it:
            it = "general"
        refs = []
        if hc.conversation_id:
            refs.append({"type": "conversation", "id": hc.conversation_id})
        if hc.message_id:
            refs.append({"type": "message", "id": hc.message_id})
        refs.append({"type": "correction", "id": hc.id})
        _emit_pattern(it, "hc", f"Review corrections for {it}; consider prompt/rule tuning", refs, hc.mode or "")
        count += 1
        sales = getattr(hc, "sales_linkage", None) or {}
        if isinstance(sales, dict):
            if sales.get("strategy"):
                _emit_pattern(
                    f"strategy:{sales['strategy']}",
                    "hc", "Improve strategy handling for this approach", refs, hc.mode or "",
                )
                count += 1
            if sales.get("objection_type"):
                _emit_pattern(
                    f"objection:{sales['objection_type']}",
                    "hc", f"Improve objection handling for {sales['objection_type']}", refs, hc.mode or "",
                )
                count += 1
            if sales.get("recommendation_quality"):
                _emit_pattern(
                    f"recommendation:{sales['recommendation_quality']}",
                    "hc", "Improve recommendation quality/match", refs, hc.mode or "",
                )
                count += 1
            if sales.get("stage_decision"):
                _emit_pattern(
                    f"stage:{sales['stage_decision']}",
                    "hc", f"Improve stage decision for {sales['stage_decision']}", refs, hc.mode or "",
                )
                count += 1

    qs_fb = ResponseFeedback.objects.filter(created_at__gte=since).filter(
        Q(is_good=False) | Q(quality="weak") | Q(quality="wrong")
    ).select_related("message", "conversation")
    for fb in qs_fb:
        it = fb.issue_type or "general"
        refs = []
        if fb.conversation_id:
            refs.append({"type": "conversation", "id": fb.conversation_id})
        if fb.message_id:
            refs.append({"type": "message", "id": fb.message_id})
        _emit_pattern(it, "fb", f"Review feedback for {it}; improve response quality", refs, fb.mode or "")
        count += 1
        if getattr(fb, "strategy", None):
            _emit_pattern(f"strategy:{fb.strategy}", "fb", "Improve strategy handling", refs, fb.mode or "")
            count += 1
        if getattr(fb, "objection_type", None):
            _emit_pattern(f"objection:{fb.objection_type}", "fb", f"Improve objection handling for {fb.objection_type}", refs, fb.mode or "")
            count += 1
        if getattr(fb, "recommendation_quality", None):
            _emit_pattern(f"recommendation:{fb.recommendation_quality}", "fb", "Improve recommendation quality", refs, fb.mode or "")
            count += 1
        if getattr(fb, "stage_decision", None):
            _emit_pattern(f"stage:{fb.stage_decision}", "fb", f"Improve stage decision for {fb.stage_decision}", refs, fb.mode or "")
            count += 1
    return count


def _aggregate_escalation_reasons(days: int, company_id: Optional[int]) -> int:
    """From Escalation.reason."""
    since = timezone.now() - timedelta(days=days)
    qs = Escalation.objects.filter(created_at__gte=since).values_list("reason", "id", "conversation_id")
    counter = Counter()
    refs_map = {}
    for reason, eid, cid in qs:
        r = reason or "unknown"
        counter[r] += 1
        if r not in refs_map:
            refs_map[r] = []
        refs = [{"type": "escalation", "id": eid}]
        if cid:
            refs.append({"type": "conversation", "id": cid})
        refs_map[r] = refs_map[r] + refs
    count = 0
    for reason, freq in counter.most_common(50):
        _upsert_signal(
            issue_type="escalation_reason",
            source_feature="support",
            pattern_key=reason,
            frequency=freq,
            affected_mode="",
            affected_intent="",
            example_refs=refs_map.get(reason, [])[:10],
            recommended_action=f"Add more FAQ knowledge or tighten guardrail for escalation trigger: {reason}",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_support_categories(days: int, company_id: Optional[int]) -> int:
    """From SupportCase.category."""
    since = timezone.now() - timedelta(days=days)
    qs = SupportCase.objects.filter(created_at__gte=since).values_list("category", "id", "conversation_id")
    counter = Counter()
    refs_map = {}
    for cat, sid, cid in qs:
        c = cat or "unknown"
        counter[c] += 1
        if c not in refs_map:
            refs_map[c] = []
        refs = [{"type": "support_case", "id": sid}]
        if cid:
            refs.append({"type": "conversation", "id": cid})
        refs_map[c] = refs_map[c] + refs
    count = 0
    for cat, freq in counter.most_common(50):
        _upsert_signal(
            issue_type="support_category",
            source_feature="support",
            pattern_key=cat,
            frequency=freq,
            affected_mode="",
            affected_intent="",
            example_refs=refs_map.get(cat, [])[:10],
            recommended_action=f"Support category confusion or high volume for '{cat}'; review triage rules",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_objection_types(days: int, company_id: Optional[int], sample_size: int = 2000) -> int:
    """From user messages via detect_objection."""
    since = timezone.now() - timedelta(days=days)
    msgs = Message.objects.filter(
        role="user",
        created_at__gte=since,
    ).values_list("content", "id", "conversation_id")[:sample_size]
    counter = Counter()
    refs_map = {}
    for content, mid, cid in msgs:
        key = detect_objection(content or "")
        if key:
            counter[key] += 1
            if key not in refs_map:
                refs_map[key] = []
            refs = [{"type": "message", "id": mid}]
            if cid:
                refs.append({"type": "conversation", "id": cid})
            refs_map[key] = refs_map[key] + refs
    count = 0
    for key, freq in counter.most_common(20):
        _upsert_signal(
            issue_type="objection_type",
            source_feature="sales",
            pattern_key=key,
            frequency=freq,
            affected_mode="",
            affected_intent="",
            example_refs=refs_map.get(key, [])[:10],
            recommended_action=f"Improve objection handling for '{key}'; add objection library content",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_low_confidence(days: int, company_id: Optional[int], sample_size: int = 1000) -> int:
    """From OrchestrationSnapshot where intent.confidence or scoring.confidence is low."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(created_at__gte=since)[:sample_size]
    count = 0
    for s in snapshots:
        intent = s.intent or {}
        scoring = s.scoring or {}
        intent_conf = intent.get("confidence") if isinstance(intent, dict) else None
        score_conf = scoring.get("confidence") if isinstance(scoring, dict) else None
        low = False
        if isinstance(intent_conf, (int, float)) and intent_conf < 0.6:
            low = True
        if isinstance(score_conf, (int, float)) and score_conf < 0.6:
            low = True
        if not low:
            continue
        primary = intent.get("primary", "unknown") if isinstance(intent, dict) else "unknown"
        refs = [{"type": "snapshot", "id": s.id}]
        if s.conversation_id:
            refs.append({"type": "conversation", "id": s.conversation_id})
        _upsert_signal(
            issue_type="low_confidence",
            source_feature="orchestration",
            pattern_key=primary,
            frequency=1,
            affected_mode=s.mode or "",
            affected_intent=primary,
            example_refs=refs,
            recommended_action=f"Low confidence for intent '{primary}'; improve classification or add clarification prompts",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_missing_qualification(days: int, company_id: Optional[int]) -> int:
    """From LeadQualification - count missing budget, property_type, location, timeline."""
    since = timezone.now() - timedelta(days=days)
    quals = LeadQualification.objects.filter(created_at__gte=since)
    counter = Counter()
    refs_map = {}
    for q in quals:
        for attr, key, _ in QUALIFICATION_FIELDS:
            val = getattr(q, attr, None)
            if val is None or (isinstance(val, str) and not str(val).strip()):
                counter[key] += 1
                if key not in refs_map:
                    refs_map[key] = []
                refs_map[key].append({"type": "qualification", "id": q.id})
    count = 0
    for key, freq in counter.most_common(20):
        _upsert_signal(
            issue_type="missing_qualification",
            source_feature="qualification",
            pattern_key=key,
            frequency=freq,
            affected_mode="",
            affected_intent="",
            example_refs=refs_map.get(key, [])[:10],
            recommended_action=f"Improve qualification logic for {key}; add extraction prompts or fallback questions",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_score_routing_disagreement(days: int, company_id: Optional[int], sample_size: int = 500) -> int:
    """From OrchestrationSnapshot: route=sales but temperature=cold, or route=support but intent is purchase."""
    since = timezone.now() - timedelta(days=days)
    snapshots = OrchestrationSnapshot.objects.filter(created_at__gte=since)[:sample_size]
    count = 0
    for s in snapshots:
        routing = s.routing or {}
        scoring = s.scoring or {}
        intent = s.intent or {}
        route = (routing.get("route") or "").lower()
        temp = (scoring.get("temperature") or "").lower()
        primary = intent.get("primary", "") if isinstance(intent, dict) else ""
        primary_lower = (primary or "").lower()
        disagree = False
        pattern = ""
        if route == "sales" and temp in ("cold", "nurture", "unqualified"):
            disagree = True
            pattern = "sales_routed_cold_score"
        if route == "support" and any(x in primary_lower for x in ("purchase", "project", "price")):
            disagree = True
            pattern = "support_routed_purchase_intent"
        if not disagree:
            continue
        refs = [{"type": "snapshot", "id": s.id}]
        if s.conversation_id:
            refs.append({"type": "conversation", "id": s.conversation_id})
        _upsert_signal(
            issue_type="score_routing_disagreement",
            source_feature="scoring",
            pattern_key=pattern,
            frequency=1,
            affected_mode=s.mode or "",
            affected_intent=primary,
            example_refs=refs,
            recommended_action="Sales scoring rule may need adjustment; or routing logic for score/intent mismatch",
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_reinforcement_signals(days: int, company_id: Optional[int]) -> int:
    """From ReinforcementSignal - upsert into ImprovementSignal for insights."""
    try:
        qs = list(get_reinforcement_signals_for_insights(days=days, company_id=company_id)[:2000])
    except Exception:
        return 0
    count = 0
    for rs in qs:
        refs = []
        if rs.conversation_id:
            refs.append({"type": "conversation", "id": rs.conversation_id})
        if rs.message_id:
            refs.append({"type": "message", "id": rs.message_id})
        refs.append({"type": "reinforcement_signal", "id": rs.id})
        pattern_key = rs.signal_type
        if rs.metadata and isinstance(rs.metadata, dict):
            obj_key = rs.metadata.get("objection_key") or rs.metadata.get("reason") or ""
            if obj_key:
                pattern_key = f"{rs.signal_type}:{obj_key}"
        action_map = {
            "user_continued_conversation": "Positive: user re-engaged; maintain approach",
            "user_requested_visit": "Positive: visit request; strengthen CTA",
            "user_asked_for_agent": "Handoff: user wanted human; review escalation triggers",
            "user_disengaged": "Negative: user stopped replying; review nurture/pace",
            "objection_unresolved": "Objection not resolved; improve objection handling",
            "recommendation_clicked_accepted": "Positive: recommendation accepted; reinforce matching",
            "support_escalation": "Support escalated; review triage and knowledge",
            "human_correction": "Human corrected response; review prompt/rule",
        }
        recommended = action_map.get(rs.signal_type, f"Reinforcement signal: {rs.signal_type}")
        _upsert_signal(
            issue_type="reinforcement_outcome",
            source_feature="orchestration",
            pattern_key=pattern_key,
            frequency=1,
            affected_mode="",
            affected_intent=rs.intent_primary or "",
            example_refs=refs,
            recommended_action=recommended,
            company_id=company_id,
        )
        count += 1
    return count


def _aggregate_failed_recommendation(days: int, company_id: Optional[int]) -> int:
    """Conversations with both Recommendation and Escalation - project recommended but led to escalation."""
    since = timezone.now() - timedelta(days=days)
    convs_with_rec = set(
        Recommendation.objects.filter(created_at__gte=since)
        .values_list("conversation_id", flat=True)
    )
    convs_with_esc = set(
        Escalation.objects.filter(created_at__gte=since)
        .values_list("conversation_id", flat=True)
    )
    overlap = convs_with_rec & convs_with_esc
    if not overlap:
        return 0
    proj_counter = Counter()
    for cid in overlap:
        if cid is None:
            continue
        projs = list(
            Recommendation.objects.filter(conversation_id=cid)
            .values_list("project_id", flat=True)
        )
        for pid in projs:
            proj_counter[pid] += 1
    count = 0
    overlap_list = [x for x in overlap if x is not None][:5]
    for pid, freq in proj_counter.most_common(10):
        _upsert_signal(
            issue_type="failed_recommendation",
            source_feature="recommendation",
            pattern_key=f"project_{pid}",
            frequency=freq,
            affected_mode="",
            affected_intent="",
            example_refs=[{"type": "conversation", "id": cid} for cid in overlap_list],
            recommended_action=f"Recommendation weak spot: project {pid} often leads to escalation; review match criteria or add FAQ knowledge",
            company_id=company_id,
        )
        count += 1
    return count


@transaction.atomic
def aggregate_improvement_signals(
    *,
    days: int = 30,
    company_id: Optional[int] = None,
) -> dict:
    """
    Aggregate improvement signals from persisted data.
    Returns counts per aggregation type.
    """
    cid = company_id or _get_default_company_id()
    counts = {
        "corrected_responses": _aggregate_corrected_responses(days, cid),
        "escalation_reasons": _aggregate_escalation_reasons(days, cid),
        "support_categories": _aggregate_support_categories(days, cid),
        "objection_types": _aggregate_objection_types(days, cid),
        "low_confidence": _aggregate_low_confidence(days, cid),
        "missing_qualification": _aggregate_missing_qualification(days, cid),
        "score_routing_disagreement": _aggregate_score_routing_disagreement(days, cid),
        "failed_recommendation": _aggregate_failed_recommendation(days, cid),
        "reinforcement_signals": _aggregate_reinforcement_signals(days, cid),
    }
    sales_counts = aggregate_sales_agent_insights(days=days, company_id=cid)
    counts.update(sales_counts)
    return counts
