"""
Operator Assist - build AI intelligence stack context for human operators.
Provides lead score, buyer stage, missing qual fields, next action, recommendations,
objection hints, and reasoning summary for the conversation workspace.
"""
from typing import Optional

from engines.objection_library import OBJECTIONS, detect_objection

# Short operator hints per objection key (concise, actionable)
OBJECTION_HINTS: dict[str, str] = {
    "price_too_high": "Value framing; offer flexible plans or projects in their budget",
    "location_concern": "Explain tradeoffs; suggest sites in their preferred area",
    "trust_credibility": "Share track record; offer site visit or testimonials",
    "payment_plan_mismatch": "Multiple plans available; ask comfortable monthly payment",
    "investment_uncertainty": "Share area data; clarify residential vs commercial focus",
    "waiting_hesitation": "No pressure; offer materials and reconnect when ready",
    "comparing_projects": "Highlight key differences; offer comparison site visit",
    "delivery_concerns": "Share known timelines; offer to arrange phase clarity",
}

# Qualification field labels
QUAL_FIELDS = [
    ("budget_min", "Budget min"),
    ("budget_max", "Budget max"),
    ("property_type", "Property type"),
    ("location_preference", "Location"),
    ("timeline", "Timeline"),
]


def _get_missing_qualification_fields(qual) -> list[str]:
    """Return list of missing qualification field labels."""
    if qual is None:
        return [label for _, label in QUAL_FIELDS]
    missing = []
    for attr, label in QUAL_FIELDS:
        val = getattr(qual, attr, None)
        if val is None or (isinstance(val, str) and not str(val).strip()):
            missing.append(label)
    return missing


def _get_objection_hints_from_messages(messages, max_recent: int = 10) -> list[dict]:
    """
    Scan recent user messages for objections and return hints.
    Returns list of {"objection_key": str, "hint": str}.
    """
    if not messages:
        return []
    user_msgs = [m for m in messages if getattr(m, "role", "") == "user"][-max_recent:]
    seen = set()
    hints = []
    for msg in reversed(user_msgs):
        content = getattr(msg, "content", "") or ""
        key = detect_objection(content)
        if key and key not in seen:
            seen.add(key)
            hint_str = OBJECTION_HINTS.get(key)
            if not hint_str:
                obj = OBJECTIONS.get(key)
                hint_str = getattr(obj, "response_en", str(obj))[:80] if obj else key.replace("_", " ").title()
            hints.append({
                "objection_key": key,
                "label": key.replace("_", " ").title(),
                "hint": hint_str,
            })
    return hints[:5]  # Top 5 most recent


def _build_reasoning_summary(snapshot, score) -> str:
    """Build concise reasoning summary from snapshot and/or score."""
    parts = []
    if snapshot:
        scoring = getattr(snapshot, "scoring", None) or {}
        if isinstance(scoring, dict):
            reason_codes = scoring.get("reason_codes") or scoring.get("explanation") or []
            for r in (reason_codes or [])[:3]:
                note = r.get("note") or r.get("factor") if isinstance(r, dict) else ""
                if note:
                    parts.append(str(note)[:60])
        routing = getattr(snapshot, "routing", None) or {}
        if isinstance(routing, dict):
            stage_reason = routing.get("stage_reasoning")
            if stage_reason and isinstance(stage_reason, list):
                parts.extend(str(x)[:50] for x in stage_reason[:2])
            next_move = routing.get("next_sales_move")
            if next_move:
                parts.append(str(next_move)[:60])
    if score and not parts:
        expl = getattr(score, "explanation", None) or []
        for e in (expl or [])[:3]:
            note = e.get("note") or e.get("factor") if isinstance(e, dict) else ""
            if note:
                parts.append(str(note)[:60])
    return " | ".join(parts[:4]) if parts else ""


def build_operator_assist(
    *,
    conversation,
    latest_snapshot,
    latest_score,
    latest_qual,
    messages,
    recommendations,
    escalations,
    support_cases,
) -> dict:
    """
    Build operator assist context for the conversation workspace.
    Returns dict with: lead_score, buyer_stage, missing_qualification_fields,
    best_next_action, top_recommendations, objection_hints, reasoning_summary,
    has_escalation, has_support_case, escalation_ids, support_case_ids.
    """
    lead_score = None
    if latest_score:
        lead_score = {
            "value": latest_score.score,
            "temperature": getattr(latest_score, "temperature", None) or "",
        }

    buyer_stage = ""
    if latest_snapshot and getattr(latest_snapshot, "journey_stage", None):
        buyer_stage = latest_snapshot.journey_stage
    elif latest_score and getattr(latest_score, "journey_stage", None):
        buyer_stage = latest_score.journey_stage

    missing_qual = _get_missing_qualification_fields(latest_qual)

    best_next_action = ""
    if latest_snapshot:
        nba = getattr(latest_snapshot, "next_best_action", None) or ""
        routing = getattr(latest_snapshot, "routing", None) or {}
        if isinstance(routing, dict) and routing.get("next_sales_move"):
            best_next_action = routing.get("next_sales_move") or nba
        if not best_next_action:
            best_next_action = nba
    if not best_next_action and latest_score:
        best_next_action = getattr(latest_score, "next_best_action", "") or ""

    top_recommendations = []
    for rec in (recommendations or [])[:5]:
        proj = getattr(rec, "project", None)
        top_recommendations.append({
            "project_name": proj.name if proj else "—",
            "project_id": proj.id if proj else None,
            "rationale": (getattr(rec, "rationale", "") or "")[:100],
        })

    objection_hints = _get_objection_hints_from_messages(messages or [])

    reasoning_summary = _build_reasoning_summary(latest_snapshot, latest_score)

    esc_ids = [e.id for e in (escalations or []) if e.id]
    sup_ids = [s.id for s in (support_cases or []) if s.id]

    return {
        "lead_score": lead_score,
        "buyer_stage": buyer_stage,
        "missing_qualification_fields": missing_qual,
        "best_next_action": best_next_action,
        "top_recommendations": top_recommendations,
        "objection_hints": objection_hints,
        "reasoning_summary": reasoning_summary,
        "has_escalation": len(esc_ids) > 0,
        "has_support_case": len(sup_ids) > 0,
        "escalation_ids": esc_ids,
        "support_case_ids": sup_ids,
        "escalations": escalations or [],
        "support_cases": support_cases or [],
    }
