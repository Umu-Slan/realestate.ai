"""
Production-leaning deterministic lead scoring engine for Egyptian real estate.
All rules inspectable in code. Weights total 100. Supports hot, warm, cold, nurture, unqualified, spam.
"""
from decimal import Decimal
from typing import Optional

from core.enums import LeadTemperature, SourceChannel
from intelligence.schemas import QualificationExtraction, ScoringResult, ReasonCode, IntentResult


# --- WEIGHTS (total 100) ---
BUDGET_CLARITY_MAX = 10
BUDGET_FIT_MAX = 10
LOCATION_FIT_MAX = 10
PROJECT_FIT_MAX = 10
URGENCY_MAX = 8
PURCHASE_TIMELINE_MAX = 6
FINANCING_READINESS_MAX = 8
ENGAGEMENT_STRENGTH_MAX = 12
DECISION_AUTHORITY_MAX = 6
RETURNING_INTEREST_MAX = 6
ACTION_SIGNALS_MAX = 8
SOURCE_QUALITY_MAX = 6

# --- THRESHOLDS ---
HOT_MIN = 75
WARM_MIN = 55
COLD_MIN = 35
NURTURE_MIN = 20
# Below NURTURE_MIN = unqualified (0-19)

# Source quality tier (higher = better lead source)
SOURCE_QUALITY_TIERS = {
    SourceChannel.CRM_IMPORT.value: 6,
    SourceChannel.PHONE.value: 5,
    SourceChannel.WHATSAPP.value: 4,
    SourceChannel.EMAIL.value: 4,
    SourceChannel.WEB.value: 3,
    SourceChannel.INSTAGRAM.value: 3,
    SourceChannel.API.value: 3,
    SourceChannel.DEMO.value: 2,
}


def score_lead(
    qualification: QualificationExtraction,
    intent: IntentResult,
    *,
    is_returning: bool = False,
    message_count: int = 1,
    has_project_match: bool = False,
    decision_authority_signals: bool = False,
    source_channel: str = "",
) -> ScoringResult:
    """
    Deterministic Egyptian real estate lead scoring.
    Returns score 0-100, temperature, confidence, reason_codes, missing_fields, next_best_action.
    """
    reasons: list[ReasonCode] = []
    points = 0

    # Spam/broker bypass - do not score
    if intent.is_spam:
        return _spam_result()
    if intent.is_broker:
        return _broker_result()

    # 1. Budget clarity (0-10)
    bc = _score_budget_clarity(qualification, reasons)
    points += bc

    # 2. Budget fit (0-10)
    bf = _score_budget_fit(qualification, reasons)
    points += bf

    # 3. Location fit (0-10)
    lf = _score_location_fit(qualification, reasons)
    points += lf

    # 4. Project fit (0-10)
    pf = _score_project_fit(qualification, has_project_match, reasons)
    points += pf

    # 5. Urgency (0-8)
    u = _score_urgency(qualification, reasons)
    points += u

    # 6. Purchase timeline (0-6)
    pt = _score_purchase_timeline(qualification, reasons)
    points += pt

    # 7. Financing readiness (0-8)
    fr = _score_financing_readiness(qualification, reasons)
    points += fr

    # 8. Engagement strength (0-12) - intent + message count
    es = _score_engagement_strength(intent, message_count, reasons)
    points += es

    # 9. Decision authority (0-6)
    da = DECISION_AUTHORITY_MAX if decision_authority_signals else 0
    if da:
        reasons.append(ReasonCode("decision_authority", da, "Decision-maker signals"))
    points += da

    # 10. Returning interest (0-6)
    ri = RETURNING_INTEREST_MAX if is_returning else 0
    if ri:
        reasons.append(ReasonCode("returning_interest", ri, "Returning engagement"))
    points += ri

    # 11. Action signals - viewing/brochure/callback (0-8)
    ac = _score_action_signals(intent, reasons)
    points += ac

    # 12. Source quality (0-6)
    sq = _score_source_quality(source_channel, reasons)
    points += sq

    points = min(100, max(0, points))

    # Temperature
    temp = _points_to_temperature(points)

    # Confidence
    missing = qualification.missing_fields or []
    if len(missing) <= 2:
        confidence = "high"
    elif len(missing) <= 4:
        confidence = "medium"
    else:
        confidence = "low"

    # Next best action
    next_action = _next_best_action(temp, intent, qualification, missing)

    # Recommended route
    route = _recommended_route(temp, intent)

    return ScoringResult(
        score=points,
        temperature=temp,
        confidence=confidence,
        reason_codes=reasons,
        missing_fields=missing,
        next_best_action=next_action,
        recommended_route=route,
    )


def _spam_result() -> ScoringResult:
    return ScoringResult(
        score=0,
        temperature=LeadTemperature.SPAM.value,
        confidence="high",
        reason_codes=[ReasonCode("spam", 0, "Spam detected")],
        missing_fields=[],
        next_best_action="Quarantine",
        recommended_route="quarantine",
    )


def _broker_result() -> ScoringResult:
    return ScoringResult(
        score=0,
        temperature=LeadTemperature.COLD.value,
        confidence="high",
        reason_codes=[ReasonCode("broker", 0, "Broker inquiry")],
        missing_fields=[],
        next_best_action="Route to broker team",
        recommended_route="broker",
    )


def _score_budget_clarity(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    if q.budget_clarity == "explicit_range":
        reasons.append(ReasonCode("budget_clarity", BUDGET_CLARITY_MAX, "Explicit budget range given"))
        return BUDGET_CLARITY_MAX
    if q.budget_clarity == "approximate":
        v = 6
        reasons.append(ReasonCode("budget_clarity", v, "Approximate budget indicated"))
        return v
    reasons.append(ReasonCode("budget_clarity", 0, "Budget not specified"))
    return 0


def _score_budget_fit(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    if q.budget_min and q.budget_max:
        reasons.append(ReasonCode("budget_fit", BUDGET_FIT_MAX, "Budget range within typical market"))
        return BUDGET_FIT_MAX
    if q.budget_min or q.budget_max:
        v = 5
        reasons.append(ReasonCode("budget_fit", v, "Partial budget indicated"))
        return v
    reasons.append(ReasonCode("budget_fit", 0, "No budget constraint"))
    return 0


def _score_location_fit(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    loc = (q.location_preference or "").strip()
    if not loc:
        reasons.append(ReasonCode("location_fit", 0, "Location not specified"))
        return 0
    # Specific area (New Cairo, المعادي, October, etc.)
    specific = any(
        x in loc.lower()
        for x in ["new cairo", "المعادي", "معادي", "october", "أكتوبر", "zamalek", "zamalek", "6th october", "sheikh zayed"]
    )
    if specific or len(loc.split()) >= 2:
        reasons.append(ReasonCode("location_fit", LOCATION_FIT_MAX, f"Specific area: {loc[:50]}"))
        return LOCATION_FIT_MAX
    v = 5
    reasons.append(ReasonCode("location_fit", v, f"General area: {loc[:30]}"))
    return v


def _score_project_fit(q: QualificationExtraction, has_match: bool, reasons: list[ReasonCode]) -> int:
    if has_match or (q.project_preference and len(q.project_preference) > 3):
        reasons.append(ReasonCode("project_fit", PROJECT_FIT_MAX, "Specific project interest"))
        return PROJECT_FIT_MAX
    if q.project_preference:
        v = 5
        reasons.append(ReasonCode("project_fit", v, "General project interest"))
        return v
    reasons.append(ReasonCode("project_fit", 0, "No project specified"))
    return 0


def _score_urgency(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    u = (q.urgency or "").lower()
    if u == "immediate":
        reasons.append(ReasonCode("urgency", URGENCY_MAX, "Immediate buying intent"))
        return URGENCY_MAX
    if u == "soon":
        v = 5
        reasons.append(ReasonCode("urgency", v, "Near-term interest"))
        return v
    if u == "exploring":
        v = 3
        reasons.append(ReasonCode("urgency", v, "Exploring phase"))
        return v
    reasons.append(ReasonCode("urgency", 0, "Urgency unknown"))
    return 0


def _score_purchase_timeline(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    t = (q.purchase_timeline or "").lower()
    if not t:
        reasons.append(ReasonCode("purchase_timeline", 0, "Timeline unknown"))
        return 0
    if "1 month" in t or "شهر" in t or "فوراً" in t or "now" in t:
        reasons.append(ReasonCode("purchase_timeline", PURCHASE_TIMELINE_MAX, "Within 1 month"))
        return PURCHASE_TIMELINE_MAX
    if "3" in t or "6" in t or "12" in t or "شهور" in t or "months" in t:
        v = 4
        reasons.append(ReasonCode("purchase_timeline", v, "3-12 months"))
        return v
    if "year" in t or "سنة" in t:
        v = 2
        reasons.append(ReasonCode("purchase_timeline", v, "12+ months"))
        return v
    v = 2
    reasons.append(ReasonCode("purchase_timeline", v, "Timeline indicated"))
    return v


def _score_financing_readiness(q: QualificationExtraction, reasons: list[ReasonCode]) -> int:
    fr = (q.financing_readiness or "").lower()
    if fr == "ready":
        reasons.append(ReasonCode("financing_readiness", FINANCING_READINESS_MAX, "Financing ready"))
        return FINANCING_READINESS_MAX
    if fr == "exploring":
        v = 4
        reasons.append(ReasonCode("financing_readiness", v, "Exploring financing"))
        return v
    if fr == "not_ready":
        v = 2
        reasons.append(ReasonCode("financing_readiness", v, "Financing not ready"))
        return v
    if q.payment_method in ("cash", "كاش"):
        v = 5
        reasons.append(ReasonCode("financing_readiness", v, "Cash payment indicated"))
        return v
    reasons.append(ReasonCode("financing_readiness", 0, "Financing unknown"))
    return 0


def _score_engagement_strength(intent: IntentResult, message_count: int, reasons: list[ReasonCode]) -> int:
    primary = (intent.primary or "").lower()
    high_intent = primary in [
        "property_purchase", "investment_inquiry", "schedule_visit",
        "price_inquiry", "brochure_request",
    ]
    med_intent = primary in ["project_inquiry", "location_inquiry", "installment_inquiry"]
    intent_pts = 8 if high_intent else 5 if med_intent else 2
    msg_pts = min(4, message_count * 1)
    total = min(ENGAGEMENT_STRENGTH_MAX, intent_pts + msg_pts)
    if total:
        note = "High intent" if high_intent else "Medium intent" if med_intent else "Low intent"
        reasons.append(ReasonCode("engagement_strength", total, f"{note}, {message_count} msg(s)"))
    return total


def _score_action_signals(intent: IntentResult, reasons: list[ReasonCode]) -> int:
    primary = (intent.primary or "").lower()
    if "schedule_visit" in primary or "visit" in primary:
        reasons.append(ReasonCode("action_signals", ACTION_SIGNALS_MAX, "Viewing/site visit requested"))
        return ACTION_SIGNALS_MAX
    if "brochure_request" in primary or "brochure" in primary:
        v = 6
        reasons.append(ReasonCode("action_signals", v, "Brochure requested"))
        return v
    if "price_inquiry" in primary or "price" in primary:
        v = 5
        reasons.append(ReasonCode("action_signals", v, "Price/callback signal"))
        return v
    if "property_purchase" in primary or "investment" in primary:
        v = 6
        reasons.append(ReasonCode("action_signals", v, "Purchase/investment intent"))
        return v
    reasons.append(ReasonCode("action_signals", 0, "No strong action signal"))
    return 0


def _score_source_quality(channel: str, reasons: list[ReasonCode]) -> int:
    ch = (channel or "").lower()
    pts = SOURCE_QUALITY_TIERS.get(ch, 2)
    reasons.append(ReasonCode("source_quality", pts, f"Source: {ch or 'unknown'}"))
    return pts


def _points_to_temperature(points: int) -> str:
    if points >= HOT_MIN:
        return LeadTemperature.HOT.value
    if points >= WARM_MIN:
        return LeadTemperature.WARM.value
    if points >= COLD_MIN:
        return LeadTemperature.COLD.value
    if points >= NURTURE_MIN:
        return LeadTemperature.NURTURE.value
    return LeadTemperature.UNQUALIFIED.value


def _next_best_action(temp: str, intent: IntentResult, q: QualificationExtraction, missing: list[str]) -> str:
    primary = (intent.primary or "").lower()
    if temp == LeadTemperature.HOT.value:
        if "schedule_visit" in primary or "visit" in primary:
            return "Schedule site visit immediately"
        return "Qualify further and schedule visit"
    if temp == LeadTemperature.WARM.value:
        if "brochure" in primary:
            return "Send brochure and follow up"
        return "Send project details and follow up"
    if temp == LeadTemperature.COLD.value:
        return "Nurture with content, clarify needs"
    if temp == LeadTemperature.NURTURE.value:
        return "Educate and qualify over time"
    if temp == LeadTemperature.UNQUALIFIED.value:
        if "budget" in str(missing).lower():
            return "Ask for budget range"
        if "location" in str(missing).lower():
            return "Ask for preferred area"
        return "Engage to qualify"
    return "Review and route"


def _recommended_route(temp: str, intent: IntentResult) -> str:
    primary = (intent.primary or "").lower()
    if temp == LeadTemperature.HOT.value:
        return "senior_sales" if ("visit" in primary or "schedule" in primary) else "sales"
    if temp == LeadTemperature.WARM.value:
        return "sales"
    if temp in (LeadTemperature.COLD.value, LeadTemperature.NURTURE.value, LeadTemperature.UNQUALIFIED.value):
        return "nurture"
    return "nurture"
