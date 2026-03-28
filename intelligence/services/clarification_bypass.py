"""
When lead scoring marks confidence \"low\" due to many missing qualification fields,
we still route to clarification. Strong user wording or clear intent should keep the
sales path so the assistant can qualify in-context instead of a generic clarify loop.
"""
from __future__ import annotations

from typing import Sequence

from intelligence.schemas import IntentResult, RoutingDecision, ScoringResult

# Intents that justify continuing sales even with sparse qualification
_CLEAR_SALES_INTENTS = frozenset(
    {
        "property_purchase",
        "project_inquiry",
        "schedule_visit",
        "price_inquiry",
        "brochure_request",
        "installment_inquiry",
        "location_inquiry",
        "investment_inquiry",
    }
)

# Arabic / English tokens that indicate real buying interest (not noise)
_LEXICAL_AR = (
    "رشح",
    "رشّح",
    "ترشيح",
    "اعرض",
    "اعرضلي",
    "عرض المشاريع",
    "مشاريع مناسبة",
    "ميزانيت",
    "ميزانية",
    "معاين",
    "معاينة",
    "موعد",
    "أثبت",
    "اثبت",
    "احجز",
    "حجز",
    "زيارة",
    "شقة",
    "فيلا",
    "دوبلكس",
    "وحدة",
    "اشتري",
    "أشتري",
    "شراء",
    "سعر",
    "اسعار",
    "السعر",
    "تقسيط",
    "قسط",
    "العاشرة",
    "الصباح",
    "الرابعة",
    "صباحاً",
    "عصراً",
    "مساءً",
    "ثلاثاء",
    "أحد",
    "اثنين",
    "خميس",
    "جمعة",
    "سبت",
)
_LEXICAL_EN = (
    "recommend",
    "budget",
    "visit",
    "schedule",
    "apartment",
    "price",
    "buy",
    "duplex",
    "villa",
    "unit",
    "pm",
    " am",
)


def _text_lower(s: str) -> str:
    return (s or "").lower()


def message_has_strong_lead_lexical_signal(message_text: str) -> bool:
    t = _text_lower(message_text)
    if any(x in t for x in _LEXICAL_AR):
        return True
    tl = f" {t} "
    return any(x in tl for x in _LEXICAL_EN)


def visit_scheduling_continuation(
    conversation_history: Sequence[dict] | None,
    message_text: str,
) -> bool:
    """Assistant asked about a visit; user replies with day/time or confirm wording."""
    history = list(conversation_history or [])
    if len(history) < 1:
        return False
    last_assistant = ""
    for msg in reversed(history):
        if (msg.get("role") or "").lower() == "assistant":
            last_assistant = _text_lower(msg.get("content") or "")
            break
    if not last_assistant:
        return False
    visit_cues = ("معاينة", "معاينه", "زيارة", "visit", "site visit", "موعدك", "يناسبك")
    if not any(c in last_assistant for c in visit_cues):
        return False
    u = _text_lower(message_text)
    time_cues = (
        "صباح",
        "عصر",
        "مساء",
        "العاشرة",
        "الرابعة",
        "الثالثة",
        "الثانية",
        "الواحدة",
        "pm",
        "am",
        "ثلاثاء",
        "أحد",
        "اثنين",
        "خميس",
        "جمعة",
        "سبت",
        "بين",
        "يوم",
    )
    confirm_cues = ("أثبت", "اثبت", "ثبت", "موعد", "معاينة", "confirm", "book")
    return any(c in u for c in time_cues) or any(c in u for c in confirm_cues)


def should_skip_low_confidence_clarification(
    intent: IntentResult,
    message_text: str,
    scoring: ScoringResult | None,
    conversation_history: Sequence[dict] | None = None,
) -> bool:
    """True => do not force clarification solely because scoring.confidence is low."""
    if scoring is None or (scoring.confidence or "").lower() != "low":
        return False

    if message_has_strong_lead_lexical_signal(message_text):
        return True
    if visit_scheduling_continuation(conversation_history, message_text):
        return True

    primary = (intent.primary or "").lower()
    conf = float(getattr(intent, "confidence", 0) or 0)
    if primary in _CLEAR_SALES_INTENTS and conf >= 0.45:
        return True
    return False


def relax_clarification_routing_if_applicable(
    routing: RoutingDecision,
    intent: IntentResult,
    scoring: ScoringResult,
    message_text: str,
    conversation_history: Sequence[dict] | None = None,
) -> RoutingDecision:
    """If routing sent the user to clarification only due to low score confidence, optionally reopen sales."""
    if (routing.route or "").lower() != "clarification" or not routing.requires_human_review:
        return routing
    if not should_skip_low_confidence_clarification(
        intent, message_text, scoring, conversation_history
    ):
        return routing
    return RoutingDecision(
        route="sales",
        queue=routing.queue or "default",
        priority=routing.priority,
        requires_human_review=False,
        safe_response_policy=routing.safe_response_policy,
        escalation_ready=routing.escalation_ready,
        quarantine=routing.quarantine,
        handoff_type="sales",
        reason="Clear lead signals — qualify in sales flow despite sparse fields",
    )


def clarification_reply_hint(
    intent_primary: str,
    *,
    visit_flow: bool,
    lang: str,
) -> str | None:
    """Optional Arabic/English clarification copy when we truly need more detail."""
    ip = (intent_primary or "").lower()
    ar = lang == "ar"
    if visit_flow:
        return (
            "تمام — فريق المبيعات يتواصل معاك لتأكيد **موعد المعاينة** حسب الوقت اللي ذكرته. "
            "لو تحب نجهّز خيارات قبل الزيارة: ما **الميزانية التقريبية** و**المنطقة** الأنسب؟"
            if ar
            else (
                "Thanks — our team will confirm your **visit** for the time you shared. "
                "To prepare options: what **approximate budget** and **preferred area** work best?"
            )
        )
    if ip in ("schedule_visit", "property_purchase", "project_inquiry", "price_inquiry"):
        return (
            "عشان نرشّح أنسب مشروع: حدّد لي **الميزانية التقريبية**، **المنطقة**، و**نوع الوحدة** (شقة/فيلا/دوبلكس) لو تحب."
            if ar
            else (
                "To recommend the best fit, please share your **approximate budget**, **preferred area**, "
                "and **unit type** (apartment/villa/duplex) if you can."
            )
        )
    return None
