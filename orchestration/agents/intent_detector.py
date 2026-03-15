"""
Production-grade intent detection for Egyptian real estate.
Arabic-first, handles vague messages, extracts entities.
Returns true sales/support/business intent, not just keyword matches.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

# --- Intent taxonomy (sales-focused) ---
SALES_INTENTS = frozenset({
    "property_search",
    "price_inquiry",
    "location_inquiry",
    "project_details",
    "investment_inquiry",
    "visit_request",
    "booking_intent",
    "support_request",
    "negotiation",
    "unclear",
})

# --- Entity keys ---
ENTITY_KEYS = frozenset({
    "budget", "location", "property_type", "bedrooms",
    "timeline", "investment_vs_residence",
})

# --- Buyer journey stage hints ---
STAGE_HINTS = frozenset({
    "awareness", "consideration", "shortlisting",
    "visit_planning", "negotiation", "booking",
})


@dataclass
class IntentDetectionResult:
    """Output of intent detection + entity extraction."""
    intent: str
    confidence: float
    extracted_entities: dict = field(default_factory=dict)
    stage_hint: str = ""
    is_support: bool = False
    is_spam: bool = False
    is_broker: bool = False
    legacy_primary: str = "other"  # Maps to IntentCategory for routing


# --- Arabic + English patterns (Arabic-first) ---
# Format: (pattern, intent, is_support, is_spam, is_broker)
# Order matters: more specific patterns first

INTENT_PATTERNS_AR = [
    # Spam
    (r"(?:اضغط|احصل مجاناً|invest now guarantee|free money)", "unclear", False, True, False),
    (r"http[s]?://[^\s]+", "unclear", False, True, False),
    # Broker
    (r"(?:سمسار|وكلاء|شريك|كم عمولة|broker)", "unclear", False, False, True),
    # Support
    (r"(?:شكوى|complaint|مستاء|غاضب|angry|مش عاجبني|مشكلة|problem)", "support_request", True, False, False),
    (r"(?:عقد|contract|توقيع|تعديل)", "support_request", True, False, False),
    (r"(?:صيانة|maintenance|تسريب|كسر)", "support_request", True, False, False),
    (r"(?:تقسيط|قسط|installment|الشهر الجاي)", "support_request", True, False, False),
    (r"(?:تسليم|delivery|متى التوصيل|handover|استلام|ميعاد الاستلام)", "support_request", True, False, False),
    # Negotiation (price-related, deal-making)
    (r"(?:خصم|discount|تقليل|تخفيض|أقل شوية|نزل السعر|negotiate)", "negotiation", False, False, False),
    (r"(?:غالي|expensive|مكلف|أرخص|cheaper)", "negotiation", False, False, False),
    # Price inquiry
    (r"(?:السعر|سعر|السعر كام|كم التكلفة|price|cost|التكلفة|المبلغ)", "price_inquiry", False, False, False),
    (r"(?:كام|كام الفلوس|كم)", "price_inquiry", False, False, False),
    # Visit / booking
    (r"(?:حجز|book|reserve|احجز|حجز وحدة)", "booking_intent", False, False, False),
    (r"(?:زيارة|visit|جولة|tour|معاينة|أزور|زيارة الموقع)", "visit_request", False, False, False),
    (r"(?:متى أقدر أزور|أريد معاينة|schedule)", "visit_request", False, False, False),
    # Investment (before property_search: "عايز استثمار" = investment, not generic search)
    (r"(?:استثمار|investment|استثماري|عائد|return)", "investment_inquiry", False, False, False),
    # Property search (before location: "عايز شقة في المعادي" = search, not "where")
    (r"(?:شقة|apartment|وحدة|فيلا|استوديو|دوبلكس)", "property_search", False, False, False),
    (r"(?:أبحث|أريد|عايز|محتاج|looking for|need)", "property_search", False, False, False),
    (r"(?:للبيع|للشراء|for sale|buy)", "property_search", False, False, False),
    # Location (general "where" questions; city names alone = location_inquiry)
    (r"(?:الموقع|موقع|مكان|location|فيين|في أي منطقة|أين)", "location_inquiry", False, False, False),
    (r"(?:المعادي|معادي|أكتوبر|6 أكتوبر|القاهرة الجديدة|الشروق|زايد|السادات)", "location_inquiry", False, False, False),
    (r"(?:new cairo|maadi|october|sheikh zayed)", "location_inquiry", False, False, False),
    # Project details
    (r"(?:مشروع|project|المشروع|تفاصيل المشروع|تفاصيل)", "project_details", False, False, False),
    (r"(?:بروشور|brochure|كتيب|كتالوج)", "project_details", False, False, False),
]

# Vague/short - low confidence, need context
VAGUE_PATTERNS = [
    (r"^(?:hi|hello|مرحبا|أهلا|السلام)", "unclear"),
    (r"^(?:شكراً|thanks|ممتاز|تمام|ok)\s*$", "unclear"),
    (r"^[؟?.\s]+$", "unclear"),
]


def _extract_entity_budget(text: str) -> Optional[dict]:
    """Extract budget from text. Returns {min, max} or {value} in EGP."""
    t = (text or "").replace(",", "")
    # مليون، مليونين، ألف، 2.5 مليون
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:مليون|million|مليونين)", 1_000_000),
        (r"(\d+(?:\.\d+)?)\s*(?:ألف|الف|k)", 1_000),
        (r"(\d+(?:\.\d+)?)\s*m\b", 1_000_000),
        (r"من\s*(\d+(?:\.\d+)?)\s*ل[ى]?\s*(\d+(?:\.\d+)?)", None),
        (r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", None),
    ]
    for pat, mult in patterns:
        m = re.search(pat, t, re.IGNORECASE | re.UNICODE)
        if m:
            if mult and len(m.groups()) >= 1:
                val = float(m.group(1)) * mult
                return {"min": val * 0.9, "max": val * 1.1}
            if len(m.groups()) >= 2:
                return {"min": float(m.group(1)), "max": float(m.group(2))}
    return None


def _extract_entity_location(text: str) -> Optional[str]:
    """Extract location preference."""
    locations = {
        "معادي": "معادي", "maadi": "معادي", "المعادي": "معادي",
        "أكتوبر": "6 أكتوبر", "october": "6 أكتوبر", "6 october": "6 أكتوبر",
        "القاهرة الجديدة": "القاهرة الجديدة", "new cairo": "القاهرة الجديدة",
        "الشروق": "الشروق", "shorouk": "الشروق",
        "زايد": " Sheikh Zayed", "zayed": "Sheikh Zayed",
        "السادات": "السادات", "sadat": "السادات",
        "مدينة نصر": "مدينة نصر", "nasr city": "مدينة نصر",
    }
    t = (text or "").lower()
    for key, canon in locations.items():
        if key.lower() in t:
            return canon
    m = re.search(r"(?:في|منطقة|location|فيين)\s+([^\s,،.]+(?:\s+[^\s,،.]+)?)", t, re.UNICODE)
    if m:
        return m.group(1).strip()
    return None


def _extract_entity_property_type(text: str) -> Optional[str]:
    """Extract property type."""
    types_map = {
        "شقة": "apartment", "apartment": "apartment", "شقق": "apartment",
        "فيلا": "villa", "villa": "villa", "فيلات": "villa",
        "استوديو": "studio", "studio": "studio",
        "دوبلكس": "duplex", "duplex": "duplex",
        "تاون هاوس": "townhouse", "townhouse": "townhouse",
    }
    t = (text or "").lower()
    for key, val in types_map.items():
        if key in t:
            return val
    return None


def _extract_entity_bedrooms(text: str) -> Optional[int]:
    """Extract bedroom count."""
    m = re.search(r"(?:غرف[ةه]?|bedroom|rooms?)\s*(\d+)", text or "", re.IGNORECASE | re.UNICODE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:غرف[ةه]?|bedroom)", text or "", re.IGNORECASE | re.UNICODE)
    if m:
        return int(m.group(1))
    return None


def _extract_entity_timeline(text: str) -> Optional[str]:
    """Extract timeline/purchase urgency."""
    immediate = ["فوراً", "أسرع", "now", "urgent", "مستعجل", "قريب", "soon"]
    exploring = ["شهور", "سنة", "months", "year", "أفكر", "exploring"]
    t = (text or "").lower()
    for w in immediate:
        if w in t:
            return "immediate"
    for w in exploring:
        if w in t:
            return "exploring"
    return None


def _extract_entity_investment_vs_residence(text: str) -> Optional[str]:
    """Extract investment vs residence purpose."""
    t = (text or "").lower()
    if any(w in t for w in ["استثمار", "investment", "استثماري", "تأجير", "rent"]):
        return "investment"
    if any(w in t for w in ["سكن", "residence", "للعائلة", "للمعيشة"]):
        return "residence"
    return None


def _extract_entities(text: str, intent: str) -> dict:
    """Extract all applicable entities from text."""
    entities = {}
    if budget := _extract_entity_budget(text):
        entities["budget"] = budget
    if loc := _extract_entity_location(text):
        entities["location"] = loc
    if pt := _extract_entity_property_type(text):
        entities["property_type"] = pt
    if bed := _extract_entity_bedrooms(text):
        entities["bedrooms"] = bed
    if tl := _extract_entity_timeline(text):
        entities["timeline"] = tl
    if iv := _extract_entity_investment_vs_residence(text):
        entities["investment_vs_residence"] = iv
    return entities


def _map_to_legacy_intent(sales_intent: str, is_support: bool, is_spam: bool, is_broker: bool) -> str:
    """Map sales intent to IntentCategory for routing compatibility."""
    if is_spam:
        return "spam"
    if is_broker:
        return "broker_inquiry"
    if is_support or sales_intent == "support_request":
        return "general_support"
    mapping = {
        "property_search": "property_purchase",
        "price_inquiry": "price_inquiry",
        "location_inquiry": "location_inquiry",
        "project_details": "project_inquiry",
        "investment_inquiry": "investment_inquiry",
        "visit_request": "schedule_visit",
        "booking_intent": "schedule_visit",
        "negotiation": "price_inquiry",
        "unclear": "other",
    }
    return mapping.get(sales_intent, "other")


def _infer_stage_hint(intent: str, entities: dict) -> str:
    """Infer buyer journey stage hint from intent and entities."""
    if intent == "booking_intent":
        return "booking"
    if intent == "negotiation":
        return "negotiation"
    if intent == "visit_request":
        return "visit_planning"
    if intent in ("price_inquiry", "project_details") and entities.get("budget"):
        return "shortlisting"
    if intent in ("property_search", "location_inquiry", "investment_inquiry"):
        return "consideration" if entities else "awareness"
    if intent == "unclear":
        return "awareness"
    return "consideration"


def _detect_deterministic(text: str, conversation_history: list) -> IntentDetectionResult:
    """Pattern-based detection. Arabic-first."""
    t = (text or "").strip()
    if len(t) < 2:
        return IntentDetectionResult(
            intent="unclear",
            confidence=0.2,
            legacy_primary="other",
        )

    t_lower = t.lower()
    entities = _extract_entities(t, "unclear")

    # Check vague/short first
    for pat, intent in VAGUE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE | re.UNICODE):
            return IntentDetectionResult(
                intent=intent,
                confidence=0.4,
                extracted_entities=entities,
                stage_hint=_infer_stage_hint(intent, entities),
                legacy_primary="other",
            )

    # Main patterns
    for pattern, intent, is_supp, is_spam, is_broker in INTENT_PATTERNS_AR:
        if re.search(pattern, t, re.IGNORECASE | re.UNICODE):
            entities = _extract_entities(t, intent)
            legacy = _map_to_legacy_intent(intent, is_supp, is_spam, is_broker)
            return IntentDetectionResult(
                intent=intent,
                confidence=0.75,
                extracted_entities=entities,
                stage_hint=_infer_stage_hint(intent, entities),
                is_support=is_supp,
                is_spam=is_spam,
                is_broker=is_broker,
                legacy_primary=legacy,
            )

    # No match - use entity cues for intent guess
    if entities.get("budget") or entities.get("location"):
        return IntentDetectionResult(
            intent="property_search",
            confidence=0.5,
            extracted_entities=entities,
            stage_hint="consideration",
            legacy_primary="property_purchase",
        )
    return IntentDetectionResult(
        intent="unclear",
        confidence=0.35,
        extracted_entities=entities,
        stage_hint="awareness",
        legacy_primary="other",
    )


def _detect_llm(text: str, conversation_history: list, customer_type: str) -> Optional[IntentDetectionResult]:
    """LLM-based detection for ambiguous cases."""
    try:
        from intelligence.llm_client import call_llm
    except ImportError:
        return None

    history_str = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')[:80]}" for m in (conversation_history or [])[-4:]
    ) or "(none)"

    system = """You classify intent for Egyptian real estate sales (Arabic + English).
Intents: property_search, price_inquiry, location_inquiry, project_details, investment_inquiry, visit_request, booking_intent, support_request, negotiation, unclear.
Extract entities when present: budget (min/max in EGP), location, property_type, bedrooms, timeline, investment_vs_residence.
Return JSON only:
{"intent": "<intent>", "confidence": 0.0-1.0, "entities": {"budget": {"min": N, "max": N} or null, "location": "str" or null, "property_type": "str" or null, "bedrooms": N or null, "timeline": "immediate|exploring|soon" or null, "investment_vs_residence": "investment|residence" or null}, "stage_hint": "awareness|consideration|shortlisting|visit_planning|negotiation|booking", "is_support": bool, "is_spam": bool, "is_broker": bool}"""

    user = f"Customer: {customer_type or 'unknown'}\nContext:\n{history_str}\n\nMessage: {text}"
    out = call_llm(system, user)
    if not out or "intent" not in out:
        return None

    intent = out.get("intent", "unclear")
    if intent not in SALES_INTENTS:
        intent = "unclear"
    entities = out.get("entities") or {}
    entities = {k: v for k, v in entities.items() if v is not None and k in ENTITY_KEYS}
    stage = out.get("stage_hint", "")
    if stage not in STAGE_HINTS:
        stage = "consideration"
    legacy = _map_to_legacy_intent(
        intent,
        bool(out.get("is_support")),
        bool(out.get("is_spam")),
        bool(out.get("is_broker")),
    )
    return IntentDetectionResult(
        intent=intent,
        confidence=max(0.3, min(1.0, float(out.get("confidence", 0.6)))),
        extracted_entities=entities,
        stage_hint=stage,
        is_support=bool(out.get("is_support")),
        is_spam=bool(out.get("is_spam")),
        is_broker=bool(out.get("is_broker")),
        legacy_primary=legacy,
    )


def detect_intent(
    message_text: str,
    *,
    conversation_history: list | None = None,
    customer_type: str = "",
    use_llm: bool = True,
) -> IntentDetectionResult:
    """
    Detect true sales/support intent and extract entities.
    Arabic-first. Handles vague messages. Falls back to LLM when available.
    """
    text = (message_text or "").strip()
    history = list(conversation_history or [])

    if use_llm:
        llm_result = _detect_llm(text, history, customer_type)
        if llm_result and llm_result.confidence >= 0.5:
            return llm_result
        # Merge LLM entities with deterministic if LLM returned low-conf
        if llm_result and llm_result.extracted_entities:
            det = _detect_deterministic(text, history)
            merged = {**det.extracted_entities, **llm_result.extracted_entities}
            return IntentDetectionResult(
                intent=llm_result.intent,
                confidence=llm_result.confidence,
                extracted_entities=merged,
                stage_hint=llm_result.stage_hint or det.stage_hint,
                is_support=llm_result.is_support,
                is_spam=llm_result.is_spam,
                is_broker=llm_result.is_broker,
                legacy_primary=llm_result.legacy_primary,
            )

    return _detect_deterministic(text, history)
