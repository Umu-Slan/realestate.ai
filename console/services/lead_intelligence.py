"""
Lead intelligence — campaign (UTM), geo, project, and objection breakdowns.

All metrics are deterministic from persisted ORM data (no LLM required for numbers).
Executive "insights" are rule-based copy built from top/bottom segments.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext as _

from channels.attribution import campaign_bucket_label, geo_bucket_label
from console.models import OrchestrationSnapshot
from console.services.analytics import OBJECTION_LABELS, get_top_objections
from conversations.models import Conversation
from core.enums import LeadTemperature
from leads.models import LeadScore
from recommendations.models import Recommendation


def _first_conversation_per_customer_in_period(since) -> dict[int, Conversation]:
    convs = (
        Conversation.objects.filter(created_at__gte=since)
        .order_by("customer_id", "created_at")
        .iterator(chunk_size=1000)
    )
    first: dict[int, Conversation] = {}
    for c in convs:
        if c.customer_id not in first:
            first[c.customer_id] = c
    return first


def _attribution_from_conversation(conv: Conversation | None) -> dict[str, str]:
    if not conv:
        return {}
    meta = conv.metadata or {}
    att = meta.get("attribution")
    if isinstance(att, dict) and att:
        return {str(k): str(v) for k, v in att.items() if v is not None and str(v).strip()}
    return {}


def _segments_for_customer(
    customer_id: int,
    customer,
    first_conv_map: dict[int, Conversation],
) -> tuple[str, str]:
    conv = first_conv_map.get(customer_id)
    att = _attribution_from_conversation(conv)
    if not att and customer and getattr(customer, "metadata", None):
        af = (customer.metadata or {}).get("attribution_first")
        if isinstance(af, dict):
            att = {str(k): str(v) for k, v in af.items() if v is not None and str(v).strip()}
    return campaign_bucket_label(att or None), geo_bucket_label(att or None)


def _latest_leadscore_per_customer_in_period(since):
    scores = (
        LeadScore.objects.filter(created_at__gte=since)
        .select_related("customer")
        .order_by("customer_id", "-created_at")
    )
    seen: set[int] = set()
    for s in scores.iterator(chunk_size=500):
        if s.customer_id in seen:
            continue
        seen.add(s.customer_id)
        yield s


def _objections_from_snapshots(*, since, limit: int = 12) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    qs = OrchestrationSnapshot.objects.filter(created_at__gte=since).only("routing")
    for snap in qs.iterator(chunk_size=800):
        r = snap.routing or {}
        if not isinstance(r, dict):
            continue
        ok = (r.get("objection_key") or "").strip()
        if ok:
            counter[ok] += 1
    return [
        {"objection": k, "label": OBJECTION_LABELS.get(k, k.replace("_", " ").title()), "count": v}
        for k, v in counter.most_common(limit)
    ]


def _merge_objection_lists(a: list[dict], b: list[dict], *, limit: int = 12) -> list[dict[str, Any]]:
    merged: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for row in a + b:
        key = row.get("objection") or row.get("objection_key") or ""
        if not key:
            continue
        merged[key] += int(row.get("count") or 0)
        labels.setdefault(key, row.get("label") or OBJECTION_LABELS.get(key, key))
    return [
        {"objection": k, "label": labels.get(k, k), "count": v}
        for k, v in merged.most_common(limit)
    ]


def _project_intel(*, since, first_conv_map: dict[int, Conversation], limit: int = 12) -> list[dict[str, Any]]:
    rows = (
        Recommendation.objects.filter(created_at__gte=since)
        .values("project_id", "project__name", "project__location")
        .annotate(rec_count=Count("id"))
        .order_by("-rec_count")[:limit]
    )
    out = []
    for row in rows:
        pid = row["project_id"]
        cust_ids = list(
            Recommendation.objects.filter(project_id=pid, created_at__gte=since)
            .values_list("customer_id", flat=True)
            .distinct()
        )
        score_sum = 0
        score_n = 0
        hot = warm = cold = 0
        latest: dict[int, LeadScore] = {}
        for s in (
            LeadScore.objects.filter(customer_id__in=cust_ids, created_at__gte=since)
            .order_by("customer_id", "-created_at")
            .iterator()
        ):
            if s.customer_id not in latest:
                latest[s.customer_id] = s
        for s in latest.values():
            score_sum += s.score
            score_n += 1
            t = (s.temperature or "").lower()
            if t == LeadTemperature.HOT.value:
                hot += 1
            elif t == LeadTemperature.WARM.value:
                warm += 1
            else:
                cold += 1
        avg_score = round(score_sum / score_n, 1) if score_n else None
        hot_pct = round(100 * hot / score_n, 1) if score_n else None
        out.append(
            {
                "project_id": pid,
                "name": row["project__name"] or f"#{pid}",
                "location": row["project__location"] or "",
                "rec_count": row["rec_count"],
                "unique_customers": len(cust_ids),
                "scored_customers": score_n,
                "avg_lead_score": avg_score,
                "hot_pct": hot_pct,
            }
        )
    return out


def build_lead_intelligence_report(*, days: int = 30) -> dict[str, Any]:
    since = timezone.now() - timedelta(days=days)
    first_conv_map = _first_conversation_per_customer_in_period(since)

    camp_agg: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "score_sum": 0, "hot": 0, "warm": 0, "other": 0}
    )
    geo_agg: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "score_sum": 0, "hot": 0, "warm": 0, "other": 0}
    )

    for s in _latest_leadscore_per_customer_in_period(since):
        cust = s.customer
        camp, geo = _segments_for_customer(s.customer_id, cust, first_conv_map)
        for bucket, agg in ((camp, camp_agg), (geo, geo_agg)):
            # Skip empty geo label only for table noise
            if bucket == "—" and agg is geo_agg:
                bucket = _("Unknown geo")
            d = agg[bucket]
            d["n"] += 1
            d["score_sum"] += s.score
            t = (s.temperature or "").lower()
            if t == LeadTemperature.HOT.value:
                d["hot"] += 1
            elif t == LeadTemperature.WARM.value:
                d["warm"] += 1
            else:
                d["other"] += 1

    def finalize_agg(agg: dict) -> list[dict[str, Any]]:
        rows = []
        for label, d in agg.items():
            if d["n"] < 1:
                continue
            rows.append(
                {
                    "label": label,
                    "n": d["n"],
                    "avg_score": round(d["score_sum"] / d["n"], 1),
                    "hot_pct": round(100 * d["hot"] / d["n"], 1),
                    "warm_pct": round(100 * d["warm"] / d["n"], 1),
                }
            )
        rows.sort(key=lambda x: (-x["avg_score"], -x["n"]))
        return rows

    campaign_rows = finalize_agg(camp_agg)
    geo_rows = finalize_agg(geo_agg)

    objection_snapshots = _objections_from_snapshots(since=since, limit=15)
    objection_messages = get_top_objections(limit=15, days=days, sample_size=800)
    objections_combined = _merge_objection_lists(objection_snapshots, objection_messages, limit=12)

    project_rows = _project_intel(since=since, first_conv_map=first_conv_map, limit=12)

    # Conversation velocity by channel (volume)
    channel_vol = list(
        Conversation.objects.filter(created_at__gte=since)
        .values("channel")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    insights: list[str] = []
    if campaign_rows:
        best = campaign_rows[0]
        insights.append(
            _(
                "Strongest campaign segment by lead quality: “%(seg)s” — average score %(avg)s "
                "with %(hot)s%% hot among scored leads in this period."
            )
            % {"seg": best["label"], "avg": best["avg_score"], "hot": best["hot_pct"]}
        )
        if len(campaign_rows) > 1 and campaign_rows[-1]["n"] >= 3:
            weak = campaign_rows[-1]
            insights.append(
                _(
                    "Review nurturing for “%(seg)s”: lowest average score (%(avg)s) among segments "
                    "with meaningful volume — consider creative, landing page, or audience fit."
                )
                % {"seg": weak["label"], "avg": weak["avg_score"]}
            )
    if project_rows and project_rows[0].get("avg_lead_score") is not None:
        p = max(project_rows, key=lambda x: (x.get("avg_lead_score") or 0, x.get("rec_count", 0)))
        insights.append(
            _(
                "Project “%(name)s” shows the highest average lead score among recommended properties "
                "this period (where scored)."
            )
            % {"name": p["name"]}
        )
    if objections_combined:
        top = objections_combined[0]
        insights.append(
            _(
                "Top friction theme from sales snapshots & messages: %(label)s "
                "(%(n)s signals) — align scripts, proof points, and payment storytelling."
            )
            % {"label": top["label"], "n": top["count"]}
        )
    if not insights:
        insights.append(
            _(
                "Send UTM parameters and optional city/country from your web widget to enrich "
                "campaign and geo breakdowns. Example JSON fields: utm_source, utm_medium, "
                "utm_campaign, country, city."
            )
        )

    proj_chart = [p for p in project_rows if p.get("avg_lead_score") is not None][:8]

    return {
        "days": days,
        "since_iso": since.isoformat(),
        "campaign_rows": campaign_rows[:20],
        "geo_rows": geo_rows[:20],
        "objections": objections_combined,
        "projects": project_rows,
        "channel_volume": channel_vol,
        "insights": insights,
        "chart_objections_labels": [o["label"] for o in objections_combined[:8]],
        "chart_objections_counts": [o["count"] for o in objections_combined[:8]],
        "chart_channel_labels": [str(c.get("channel") or "unknown") for c in channel_vol],
        "chart_channel_counts": [int(c["n"]) for c in channel_vol],
        "chart_campaign_labels": [r["label"][:40] + ("…" if len(r["label"]) > 40 else "") for r in sorted(
            [r for r in campaign_rows if r["n"] > 0], key=lambda x: -x["n"]
        )[:8]],
        "chart_campaign_avgs": [r["avg_score"] for r in sorted(
            [r for r in campaign_rows if r["n"] > 0], key=lambda x: -x["n"]
        )[:8]],
        "chart_project_labels": [p["name"][:36] + ("…" if len(p["name"]) > 36 else "") for p in proj_chart],
        "chart_project_scores": [p["avg_lead_score"] for p in proj_chart],
    }
