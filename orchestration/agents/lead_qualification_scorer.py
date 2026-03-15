"""
Production-grade lead qualification scoring.
Uses 9 structured signals with explainable, deterministic rules.
Blends with optional LLM reasoning for edge cases.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

# --- Signal weights (total 100) ---
BUDGET_CLARITY_MAX = 12
LOCATION_CLARITY_MAX = 12
PROPERTY_TYPE_CLARITY_MAX = 10
URGENCY_MAX = 10
ENGAGEMENT_LEVEL_MAX = 12
RETURNING_BEHAVIOR_MAX = 8
VISIT_INTEREST_MAX = 10
FINANCING_READINESS_MAX = 10
DECISION_AUTHORITY_MAX = 6

# --- Thresholds ---
HOT_MIN = 75
WARM_MIN = 55
COLD_MIN = 35
NURTURE_MIN = 20


@dataclass
class ReasonCode:
    """Explainable scoring factor."""
    factor: str
    contribution: int
    note: str = ""


@dataclass
class LeadQualificationScore:
    """Scoring result with full reasoning."""
    lead_score: int
    lead_temperature: str
    reasoning: list[ReasonCode] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    next_best_action: str = ""


def _points_to_temperature(points: int) -> str:
    if points >= HOT_MIN:
        return "hot"
    if points >= WARM_MIN:
        return "warm"
    if points >= COLD_MIN:
        return "cold"
    if points >= NURTURE_MIN:
        return "nurture"
    return "unqualified"


def _score_budget_clarity(
    qualification: dict,
    intent_entities: dict,
    reasons: list[ReasonCode],
) -> int:
    """Budget clarity: explicit range > approximate > partial > none."""
    budget = intent_entities.get("budget") or qualification.get("budget_min") or qualification.get("budget_max")
    budget_extract = qualification.get("budget_min") or qualification.get("budget_max")
    if budget or budget_extract:
        if isinstance(budget, dict) and budget.get("min") and budget.get("max"):
            reasons.append(ReasonCode("budget_clarity", BUDGET_CLARITY_MAX, "Explicit budget range"))
            return BUDGET_CLARITY_MAX
        if qualification.get("budget_min") and qualification.get("budget_max"):
            reasons.append(ReasonCode("budget_clarity", BUDGET_CLARITY_MAX, "Explicit budget range"))
            return BUDGET_CLARITY_MAX
        v = 7
        reasons.append(ReasonCode("budget_clarity", v, "Approximate budget indicated"))
        return v
    reasons.append(ReasonCode("budget_clarity", 0, "Budget not specified"))
    return 0


def _score_location_clarity(
    qualification: dict,
    intent_entities: dict,
    memory_profile: dict,
    reasons: list[ReasonCode],
) -> int:
    """Location clarity: specific area > general > none."""
    loc = (
        qualification.get("location_preference")
        or (intent_entities.get("location") or "")
        or (memory_profile.get("preferred_locations") or [""])[0] if memory_profile.get("preferred_locations") else ""
    )
    loc = (loc or "").strip()
    if not loc:
        reasons.append(ReasonCode("location_clarity", 0, "Location not specified"))
        return 0
    specific = any(
        x in loc.lower()
        for x in [
            "new cairo", "المعادي", "معادي", "october", "أكتوبر", "6 أكتوبر",
            "zamalek", "sheikh zayed", "القاهرة الجديدة", "الشروق", "السادات",
        ]
    )
    if specific or len(loc.split()) >= 2:
        reasons.append(ReasonCode("location_clarity", LOCATION_CLARITY_MAX, f"Specific area: {loc[:40]}"))
        return LOCATION_CLARITY_MAX
    v = 6
    reasons.append(ReasonCode("location_clarity", v, f"Area indicated: {loc[:30]}"))
    return v


def _score_property_type_clarity(
    qualification: dict,
    intent_entities: dict,
    reasons: list[ReasonCode],
) -> int:
    """Property type: specific type > none."""
    pt = qualification.get("property_type") or intent_entities.get("property_type") or ""
    pt = (pt or "").strip().lower()
    if not pt:
        reasons.append(ReasonCode("property_type_clarity", 0, "Property type not specified"))
        return 0
    if pt in ("apartment", "villa", "studio", "duplex", "townhouse", "شقة", "فيلا", "استوديو"):
        reasons.append(ReasonCode("property_type_clarity", PROPERTY_TYPE_CLARITY_MAX, f"Type: {pt}"))
        return PROPERTY_TYPE_CLARITY_MAX
    v = 5
    reasons.append(ReasonCode("property_type_clarity", v, f"Type indicated: {pt[:30]}"))
    return v


def _score_urgency(
    qualification: dict,
    intent_entities: dict,
    reasons: list[ReasonCode],
) -> int:
    """Urgency: immediate > soon > exploring > unknown."""
    u = (qualification.get("urgency") or intent_entities.get("timeline") or "").lower()
    if "immediate" in u or "فوراً" in u or "أسرع" in u or "now" in u or "قريب" in u:
        reasons.append(ReasonCode("urgency", URGENCY_MAX, "Immediate buying intent"))
        return URGENCY_MAX
    if "soon" in u or "شهر" in u or "within" in u:
        v = 6
        reasons.append(ReasonCode("urgency", v, "Near-term interest"))
        return v
    if "exploring" in u or "شهور" in u or "سنة" in u or "months" in u or "year" in u:
        v = 3
        reasons.append(ReasonCode("urgency", v, "Exploring phase"))
        return v
    reasons.append(ReasonCode("urgency", 0, "Urgency unknown"))
    return 0


def _score_engagement_level(
    intent_primary: str,
    message_count: int,
    reasons: list[ReasonCode],
) -> int:
    """Engagement: high-intent + multi-message = stronger."""
    primary = (intent_primary or "").lower()
    high = primary in ("property_purchase", "investment_inquiry", "schedule_visit", "price_inquiry", "booking_intent")
    med = primary in ("project_inquiry", "location_inquiry", "project_details", "property_search")
    intent_pts = 8 if high else 5 if med else 2
    msg_pts = min(4, message_count)
    total = min(ENGAGEMENT_LEVEL_MAX, intent_pts + msg_pts)
    note = "High intent" if high else "Medium intent" if med else "Low intent"
    reasons.append(ReasonCode("engagement_level", total, f"{note}, {message_count} msg(s)"))
    return total


def _score_returning_behavior(
    customer_type_hint: str,
    identity_matched: bool,
    reasons: list[ReasonCode],
) -> int:
    """Returning customer = stronger signal."""
    if customer_type_hint == "returning_lead" or (identity_matched and customer_type_hint == "existing_customer"):
        reasons.append(ReasonCode("returning_behavior", RETURNING_BEHAVIOR_MAX, "Returning engagement"))
        return RETURNING_BEHAVIOR_MAX
    if identity_matched:
        v = 4
        reasons.append(ReasonCode("returning_behavior", v, "Known customer"))
        return v
    reasons.append(ReasonCode("returning_behavior", 0, "New lead"))
    return 0


def _score_visit_interest(
    intent_primary: str,
    sales_intent: str,
    reasons: list[ReasonCode],
) -> int:
    """Visit/site tour request = strong buying signal."""
    primary = (intent_primary or "").lower()
    sales = (sales_intent or "").lower()
    if "visit" in primary or "schedule" in primary or sales in ("visit_request", "booking_intent"):
        reasons.append(ReasonCode("visit_interest", VISIT_INTEREST_MAX, "Visit/site tour requested"))
        return VISIT_INTEREST_MAX
    if "brochure" in primary or "project" in primary:
        v = 5
        reasons.append(ReasonCode("visit_interest", v, "Project/brochure interest"))
        return v
    reasons.append(ReasonCode("visit_interest", 0, "No visit signal"))
    return 0


def _score_financing_readiness(
    qualification: dict,
    memory_profile: dict,
    message_text: str,
    reasons: list[ReasonCode],
) -> int:
    """Financing: ready/cash/installment > exploring > unknown."""
    fr = (qualification.get("financing_readiness") or "").lower()
    pm = (qualification.get("payment_method") or "").lower()
    mem_fin = (memory_profile.get("preferred_financing_style") or "").lower()
    txt = (message_text or "").lower()
    if fr == "ready" or pm in ("cash", "installments") or mem_fin in ("cash", "installment"):
        reasons.append(ReasonCode("financing_readiness", FINANCING_READINESS_MAX, "Financing indicated"))
        return FINANCING_READINESS_MAX
    if any(w in txt for w in ["تقسيط", "كاش", "installment", "cash", "قسط"]):
        v = 7
        reasons.append(ReasonCode("financing_readiness", v, "Payment preference mentioned"))
        return v
    if fr == "exploring":
        v = 4
        reasons.append(ReasonCode("financing_readiness", v, "Exploring financing"))
        return v
    reasons.append(ReasonCode("financing_readiness", 0, "Financing unknown"))
    return 0


def _score_decision_authority(
    message_text: str,
    reasons: list[ReasonCode],
) -> int:
    """Decision authority: explicit "I decide" / "مش محتاج أستشير" > inferred > unknown."""
    t = (message_text or "").lower()
    signals = [
        "أنا قراري", "قراري", "مش محتاج أستشير", "أنا أصدر القرار",
        "i decide", "my decision", "don't need to consult", "sole decision",
    ]
    if any(s in t for s in signals):
        reasons.append(ReasonCode("decision_authority", DECISION_AUTHORITY_MAX, "Decision-maker signals"))
        return DECISION_AUTHORITY_MAX
    reasons.append(ReasonCode("decision_authority", 0, "Decision authority unknown"))
    return 0


def _next_best_action(
    temperature: str,
    intent_primary: str,
    sales_intent: str,
    missing: list[str],
) -> str:
    """Explainable next best action."""
    primary = (intent_primary or "").lower()
    sales = (sales_intent or "").lower()
    missing_str = str(missing).lower()
    if temperature == "hot":
        if "visit" in primary or sales == "visit_request":
            return "Schedule site visit immediately"
        if sales == "booking_intent":
            return "Confirm booking and send payment plan"
        return "Qualify further and schedule visit"
    if temperature == "warm":
        if "brochure" in primary:
            return "Send brochure and follow up"
        return "Send project details and follow up"
    if temperature == "cold":
        return "Nurture with content, clarify needs"
    if temperature == "nurture":
        return "Educate and qualify over time"
    if temperature == "unqualified":
        if "budget" in missing_str:
            return "Ask for budget range"
        if "location" in missing_str:
            return "Ask for preferred area"
        if "property_type" in missing_str:
            return "Ask for property type preference"
        return "Engage to qualify"
    return "Review and route"


def _compute_missing_fields(qualification: dict, intent_entities: dict) -> list[str]:
    """Fields not yet provided."""
    missing = []
    if not (qualification.get("budget_min") or qualification.get("budget_max") or intent_entities.get("budget")):
        missing.append("budget")
    if not (qualification.get("location_preference") or intent_entities.get("location")):
        missing.append("location")
    if not (qualification.get("property_type") or intent_entities.get("property_type")):
        missing.append("property_type")
    if not qualification.get("project_preference"):
        missing.append("project")
    if not (qualification.get("urgency") or qualification.get("purchase_timeline") or intent_entities.get("timeline")):
        missing.append("timeline")
    return missing


def compute_lead_qualification_score(
    qualification: dict,
    intent_output: dict,
    *,
    message_count: int = 1,
    customer_type_hint: str = "new_lead",
    identity_matched: bool = False,
    memory_profile: Optional[dict] = None,
    message_text: str = "",
    is_spam: bool = False,
    is_broker: bool = False,
) -> LeadQualificationScore:
    """
    Compute lead score from 9 structured signals.
    Deterministic, explainable. Returns lead_score, lead_temperature, reasoning, missing_fields, next_best_action.
    """
    memory_profile = memory_profile or {}
    reasons: list[ReasonCode] = []

    if is_spam:
        return LeadQualificationScore(
            lead_score=0,
            lead_temperature="spam",
            reasoning=[ReasonCode("spam", 0, "Spam detected")],
            missing_fields=[],
            next_best_action="Quarantine",
        )
    if is_broker:
        return LeadQualificationScore(
            lead_score=0,
            lead_temperature="cold",
            reasoning=[ReasonCode("broker", 0, "Broker inquiry")],
            missing_fields=[],
            next_best_action="Route to broker team",
        )

    intent_entities = intent_output.get("entities") or {}
    intent_primary = intent_output.get("primary", "")
    sales_intent = intent_output.get("sales_intent", "")

    points = 0
    points += _score_budget_clarity(qualification, intent_entities, reasons)
    points += _score_location_clarity(qualification, intent_entities, memory_profile, reasons)
    points += _score_property_type_clarity(qualification, intent_entities, reasons)
    points += _score_urgency(qualification, intent_entities, reasons)
    points += _score_engagement_level(intent_primary, message_count, reasons)
    points += _score_returning_behavior(customer_type_hint, identity_matched, reasons)
    points += _score_visit_interest(intent_primary, sales_intent, reasons)
    points += _score_financing_readiness(qualification, memory_profile, message_text, reasons)
    points += _score_decision_authority(message_text, reasons)

    points = min(100, max(0, points))
    temperature = _points_to_temperature(points)
    missing = _compute_missing_fields(qualification, intent_entities)
    next_action = _next_best_action(temperature, intent_primary, sales_intent, missing)

    return LeadQualificationScore(
        lead_score=points,
        lead_temperature=temperature,
        reasoning=reasons,
        missing_fields=missing,
        next_best_action=next_action,
    )
