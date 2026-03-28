"""
Intent classification - LLM-assisted with deterministic fallback.
Supports multi-label intent.
"""
import re
from typing import Sequence

from core.enums import IntentCategory
from intelligence.schemas import IntentResult
from intelligence.llm_client import call_llm


# Deterministic patterns: (pattern, primary_intent, is_support, is_spam, is_broker)
# Arabic + English keywords for Egyptian real estate
INTENT_PATTERNS = [
    # Spam / noise
    (r"(?:اضغط|Click here|free money|احصل مجاناً|invest now guarantee)", IntentCategory.SPAM, False, True, False),
    (r"^(?:hi|hello|مرحبا)\s*$", IntentCategory.OTHER, False, False, False),
    # Broker
    (r"(?:سمسار|broker|وكلاء|شريك|كم عمولة)", IntentCategory.BROKER_INQUIRY, False, False, True),
    # Support
    (r"(?:شكوى|complaint|مستاء|غاضب|angry|مش عاجبني)", IntentCategory.SUPPORT_COMPLAINT, True, False, False),
    (r"(?:عقد|contract|توقيع|تعديل)", IntentCategory.CONTRACT_ISSUE, True, False, False),
    (r"(?:صيانة|maintenance|تسريب|كسر)", IntentCategory.MAINTENANCE_ISSUE, True, False, False),
    (r"(?:تقسيط|قسط|installment|الشهر الجاي)", IntentCategory.INSTALLMENT_INQUIRY, True, False, False),
    (r"(?:تسليم|delivery|متى التوصيل|ميناء|handover|تسليم الوحدة|استلام|ميعاد الاستلام)", IntentCategory.DELIVERY_INQUIRY, True, False, False),
    (r"(?:مستند|إشعار|documentation|document|طلب ورق|طلب مستند)", IntentCategory.DOCUMENTATION_INQUIRY, True, False, False),
    (r"(?:إثبات دفع|اثبات الدفع|payment proof|proof of payment)", IntentCategory.PAYMENT_PROOF_INQUIRY, True, False, False),
    # Sales intents
    (r"(?:رشح|رشّح|ترشيح|رشحلي)", IntentCategory.PROPERTY_PURCHASE, False, False, False),
    (r"عرض\s*(?:ال)?مشاريع", IntentCategory.PROJECT_INQUIRY, False, False, False),
    (r"(?:زيارة|visit|جولة|tour|معاينة)", IntentCategory.SCHEDULE_VISIT, False, False, False),
    (r"(?:بروشور|brochure|ك brochure|كتيب)", IntentCategory.BROCHURE_REQUEST, False, False, False),
    (r"(?:السعر|سعر|السعر كام|price|كم التكلفة)", IntentCategory.PRICE_INQUIRY, False, False, False),
    (r"(?:الموقع|موقع|مكان|location|فيين)", IntentCategory.LOCATION_INQUIRY, False, False, False),
    (r"(?:مشروع|project|المشروع)", IntentCategory.PROJECT_INQUIRY, False, False, False),
    (r"(?:استثمار|investment|استثماري)", IntentCategory.INVESTMENT_INQUIRY, False, False, False),
    (r"(?:شراء|شقة|وحدة|للبيع|apartment|unit)", IntentCategory.PROPERTY_PURCHASE, False, False, False),
]

SPAM_INDICATORS = [
    r"http[s]?://[^\s]+",
    r"(?:ادخل|اضغط|win|فوز)\s+(?:الآن|now)",
    r"\d{10,}",  # long number strings
]


def _deterministic_classify(text: str) -> IntentResult:
    """Fallback when LLM unavailable."""
    t = (text or "").strip().lower()
    if len(t) < 3:
        return IntentResult(primary=IntentCategory.OTHER, confidence=0.3)

    # Spam check
    for pat in SPAM_INDICATORS:
        if re.search(pat, t, re.IGNORECASE):
            return IntentResult(primary=IntentCategory.SPAM, is_spam=True, confidence=0.85)

    for pattern, intent, is_supp, is_spam, is_broker in INTENT_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE | re.UNICODE):
            return IntentResult(
                primary=intent,
                is_support=is_supp,
                is_spam=is_spam,
                is_broker=is_broker,
                confidence=0.75,
            )

    return IntentResult(primary=IntentCategory.OTHER, confidence=0.4)


def classify_intent(
    message_text: str,
    conversation_history: Sequence[dict] | None = None,
    customer_type: str = "",
    use_llm: bool = True,
) -> IntentResult:
    """
    Classify intent from message. Multi-label: primary + secondary.
    Uses LLM when available, deterministic fallback otherwise.
    """
    text = (message_text or "").strip()
    if not text:
        return IntentResult(primary=IntentCategory.OTHER, confidence=0.0)

    if use_llm:
        result = _llm_classify(text, conversation_history or [], customer_type)
        if result:
            return result

    return _deterministic_classify(text)


def _llm_classify(
    text: str,
    history: list[dict],
    customer_type: str,
) -> IntentResult | None:
    """LLM-based classification with structured output."""
    history_str = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')[:100]}" for m in history[-5:]
    ) if history else ""

    system = """You are an intent classifier for Egyptian real estate conversations.
Classify the user's intent. Support intents: support_complaint, contract_issue, maintenance_issue, delivery_inquiry, general_support.
Sales intents: property_purchase, investment_inquiry, project_inquiry, price_inquiry, location_inquiry, installment_inquiry, brochure_request, schedule_visit.
Other: broker_inquiry, spam, other.
Return JSON: {"primary": "<intent>", "secondary": ["<intent>", ...], "confidence": 0.0-1.0, "is_support": bool, "is_spam": bool, "is_broker": bool}"""

    user = f"Customer type: {customer_type or 'unknown'}\n\n"
    if history_str:
        user += f"Recent context:\n{history_str}\n\n"
    user += f"User message:\n{text}"

    out = call_llm(system, user)
    if not out or "primary" not in out:
        return None

    primary = out.get("primary", "other")
    if primary not in [c[0] for c in IntentCategory.choices]:
        primary = "other"

    return IntentResult(
        primary=primary,
        secondary=out.get("secondary", []) or [],
        confidence=float(out.get("confidence", 0.5)),
        is_support=bool(out.get("is_support")),
        is_spam=bool(out.get("is_spam")),
        is_broker=bool(out.get("is_broker")),
    )
