"""
Policy engine and guardrails.
- Blocks unsafe responses
- Rewrites into safe form
- Forces escalation
- Requests clarification
"""
import re
from dataclasses import dataclass, field
from enum import Enum


class ResponsePolicy(str, Enum):
    """Response tone/mode."""
    SALES_MODE = "sales_mode"
    SUPPORT_MODE = "support_mode"
    CLARIFICATION_MODE = "clarification_mode"
    ESCALATION_MODE = "escalation_mode"
    SAFE_ANSWER_MODE = "safe_answer_mode"
    UNAVAILABLE_DATA_MODE = "unavailable_data_mode"
    QUARANTINE = "quarantine"


def intent_primary_is_strict_price_inquiry(intent_primary: str) -> bool:
    """
    True when the intent is narrowly about pricing, not e.g. property_purchase
    (which incorrectly matched `"price" in intent` substring checks).
    """
    ip = (intent_primary or "").lower().strip()
    if not ip:
        return False
    tokens = ip.split("_")
    if "price" in tokens:
        return True
    return ip in ("pricing", "price")


class GuardrailViolation(str, Enum):
    """Detected guardrail violations."""
    UNVERIFIED_EXACT_PRICE = "unverified_exact_price"
    UNVERIFIED_EXACT_AVAILABILITY = "unverified_exact_availability"
    LEGAL_ADVICE = "legal_advice"
    PROMISE_OF_DELIVERY = "promise_of_delivery"
    INTERNAL_ONLY_INFO = "internal_company_only"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    NONE = "none"


@dataclass
class PolicyDecision:
    """Policy engine output."""
    allow_response: bool = True
    rewrite_to_safe: bool = False
    force_escalation: bool = False
    request_clarification: bool = False
    applied_policy: ResponsePolicy = ResponsePolicy.SALES_MODE
    violations: list[GuardrailViolation] = field(default_factory=list)
    safe_rewrite: str = ""
    block_reason: str = ""


# Patterns that suggest guardrail violations in draft text
# Company-safe: exact pricing only when verified, no guaranteed availability unless verified,
# no legal advice, no overpromising on delivery, no internal-only knowledge.
# Listing / exact-claim prices only. Broad "N million" without currency was firing on user budget echoes
# (e.g. "ميزانيتك 7 مليون") and wiping good Arabic replies.
PRICE_PATTERNS = [
    r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:EGP|جنيه|ج\.م|LE)\b",
    r"\b\d+(?:\.\d+)?\s*(?:million|مليون)\s+(?:EGP|جنيه|ج\.م|LE)\b",
    r"\b(?:السعر|الثمن|السعر بالضبط)\s*(?:هو|=\s*)\s*\d+",
    r"\b(?:costs?|price)\s*(?:is\s*)?\d+",
    r"\bexact (?:price|cost)\s*[:\s]*\d+",
    r"\b(?:الوحدة|unit)\s+(?:بـ|ب|تبدأ|starts?)\s*(?:من|from)?\s*[\d٬,]+",
    r"\b(?:سعر\s*الوحدة|unit\s+price)\s*[:：]?\s*[\d٬,]+",
]
AVAILABILITY_PATTERNS = [
    r"\b(?:متوفر|available|متبقى)\s*(?:\d+)\s*(?:وحدة|unit)",
    r"\b(?:last|آخر)\s+\d+\s+(?:units?|وحدات)",
    r"\b(?:guaranteed|مضمون)\s+(?:available|متوفر)",
    r"\b(?:فقط|only)\s+\d+\s+(?:وحدة|unit)s?\s*(?:متبقية|left)",
]
LEGAL_PATTERNS = [
    r"\b(?:قانوني|legal|عقد|contract)\s+(?:نصيحة|advice|توصية)",
    r"\b(?:يجب|must)\s+(?:أن|that)\s+.*(?:عقد|contract)",
    r"\b(?:هل|is)\s+(?:هذا|this)\s+(?:العقد|contract)\s+(?:صحيح|valid)",
    r"\b(?:legal advice|نصيحة قانونية|استشارة قانونية)",
    r"\b(?:contract (?:validity|valid)|صحة العقد)",
    r"\b(?:تفسير|interpretation)\s+(?:العقد|contract)",
]
DELIVERY_PROMISE_PATTERNS = [
    r"\b(?:سيتم التسليم|will be delivered|مضمون التسليم)\s+(?:في|on|by)\s+\d",
    r"\b(?:guaranteed delivery|تسليم مضمون|التسليم مضمون)",
    r"\b(?:نضمن|we guarantee)\s+(?:التسليم|delivery)",
    r"\b(?:delivery (?:by|before)\s+\d{4})",
]
INTERNAL_PATTERNS = [
    r"\b(?:internal|داخلي|للموظفين فقط)\b",
    r"\b(?:margin|هامش|عمولة)\s*[:\s]*\d+",
    r"\b(?:internal\s+)?margin\b",  # "internal margin" or "margin"
    r"\b(?:confidential|سري|للاستخدام الداخلي)\b",
    r"\b(?:cost price|سعر التكلفة)\s*[:\s]*\d+",
    r"\b(?:staff only|employees only)\b",
]
UNSUPPORTED_PATTERNS = [
    r"\b(?:best|أفضل)\s+(?:project|مشروع)\s+in\s+(?:Egypt|مصر)\b",
    r"\b(?:guaranteed returns|عائد مضمون)\s*\d+%",
    r"\b(?:أفضل استثمار|best investment)\s+in\s+",
]


def _draft_echoes_customer_budget(draft_text: str) -> bool:
    """Assistant repeats stated budget/bedrooms — allowed; not a unit listing price."""
    if not draft_text:
        return False
    if re.search(
        r"ميزانيت(?:ك|كم)|ميزانية\s*(?:العميل|التي)|your\s+budget|budget\s+you|نطاق\s*الميزانية",
        draft_text,
        re.I,
    ):
        return True
    # Qualification recap (e.g. mock LLM): "نطاق **6500000-7500000 EGP** … لبحثك"
    if re.search(r"نطاق\s*\*\*", draft_text) and re.search(
        r"(?:EGP|جنيه|ج\.م|LE|مليون)", draft_text, re.I
    ) and re.search(
        r"(?:واضح|بناءً|مناسب|بحثك|تقريبي|شكلهم)", draft_text, re.I
    ):
        return True
    if re.search(r"(?:غرف(?:ة|\s)*نوم|bedroom|غرف)", draft_text, re.I) and re.search(
        r"(?:ميزانيت|budget|مليون|million|جنيه|egp)", draft_text, re.I
    ):
        return True
    return False


def is_greeting_or_small_talk(text: str) -> bool:
    """
    True for short hello/hi messages only. Used to avoid price safe-rewrites when
    the user did not ask for pricing; draft may still contain EGP from context/LLM.
    """
    raw = re.sub(r"اًا+\s*$", "اً", (text or "").strip())
    if len(raw) > 60:
        return False
    t = re.sub(r"^[,\s!.؟،]+|[,\s!.؟،]+$", "", raw)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return False
    tl = t.lower()
    # Avoid treating "مرحبا عايز سعر" as greeting
    if len(tl) > 35:
        return False
    if re.search(r"\d", tl) and len(tl) > 12:
        return False
    greeting_res = (
        r"^مرحب[ااًً]+\s*$",
        r"^السلام\s*عليكم",
        r"^سلام\s*عليكم\s*$",
        r"^سلام\s*$",
        r"^أ?هلا+ً?\s*$",
        r"^هلا\s*$",
        r"^هاي\s*$",
        r"^hi\s*$",
        r"^hello\s*$",
        r"^hey\s*$",
        r"^good\s*(morning|afternoon|evening)\s*$",
        r"^صباح\s*الخير\s*$",
        r"^مساء\s*الخير\s*$",
        r"^thanks?\s*$",
        r"^thank\s*you\s*$",
        r"^شكرا\s*$",
        r"^شكراً\s*$",
    )
    return any(re.match(p, tl, re.I) for p in greeting_res)


def check_guardrails(
    draft_text: str,
    *,
    has_verified_pricing: bool = False,
    has_verified_availability: bool = False,
    routing: dict | None = None,
    intent: dict | None = None,
) -> list[GuardrailViolation]:
    """Scan draft for guardrail violations."""
    violations = []

    # Unverified exact price
    if not has_verified_pricing:
        for pat in PRICE_PATTERNS:
            if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
                violations.append(GuardrailViolation.UNVERIFIED_EXACT_PRICE)
                break
        if GuardrailViolation.UNVERIFIED_EXACT_PRICE in violations and _draft_echoes_customer_budget(
            draft_text or ""
        ):
            violations.remove(GuardrailViolation.UNVERIFIED_EXACT_PRICE)

    # Unverified availability
    if not has_verified_availability:
        for pat in AVAILABILITY_PATTERNS:
            if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
                violations.append(GuardrailViolation.UNVERIFIED_EXACT_AVAILABILITY)
                break

    for pat in LEGAL_PATTERNS:
        if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
            violations.append(GuardrailViolation.LEGAL_ADVICE)
            break

    for pat in DELIVERY_PROMISE_PATTERNS:
        if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
            violations.append(GuardrailViolation.PROMISE_OF_DELIVERY)
            break

    for pat in INTERNAL_PATTERNS:
        if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
            violations.append(GuardrailViolation.INTERNAL_ONLY_INFO)
            break

    for pat in UNSUPPORTED_PATTERNS:
        if re.search(pat, draft_text or "", re.IGNORECASE | re.UNICODE):
            violations.append(GuardrailViolation.UNSUPPORTED_CLAIM)
            break

    return list(set(violations))


def select_response_policy(
    customer_type: str,
    routing: dict,
    intent: dict,
    requires_clarification: bool = False,
    is_quarantine: bool = False,
) -> ResponsePolicy:
    """Select response tone based on context."""
    if is_quarantine:
        return ResponsePolicy.QUARANTINE
    route = (routing.get("route") or "").lower()
    if routing.get("force_escalation") or routing.get("escalation_ready") or route == "legal_handoff":
        return ResponsePolicy.ESCALATION_MODE
    if requires_clarification or routing.get("requires_human_review"):
        return ResponsePolicy.CLARIFICATION_MODE
    if routing.get("safe_response_policy"):
        return ResponsePolicy.SAFE_ANSWER_MODE
    if customer_type in ("support_customer", "existing_customer") and intent.get("is_support"):
        return ResponsePolicy.SUPPORT_MODE
    if routing.get("unavailable_data"):
        return ResponsePolicy.UNAVAILABLE_DATA_MODE
    return ResponsePolicy.SALES_MODE


def _policy_lang(user_message: str, draft_text: str) -> str:
    from engines.lang_utils import detect_response_language

    return detect_response_language((user_message or "") + " " + (draft_text or "")[:120])


def apply_policy_engine(
    draft_text: str,
    *,
    has_verified_pricing: bool = False,
    has_verified_availability: bool = False,
    routing: dict | None = None,
    intent: dict | None = None,
    customer_type: str = "",
    requires_clarification: bool = False,
    user_message: str = "",
    conversation_history: list | None = None,
) -> PolicyDecision:
    """
    Policy engine: block, rewrite, escalate, or allow.
    """
    routing = routing or {}
    intent = intent or {}
    lang = _policy_lang(user_message, draft_text)
    violations = check_guardrails(
        draft_text,
        has_verified_pricing=has_verified_pricing,
        has_verified_availability=has_verified_availability,
        routing=routing,
        intent=intent,
    )

    forced_greeting_reply = ""
    if user_message and is_greeting_or_small_talk(user_message):
        if GuardrailViolation.UNVERIFIED_EXACT_PRICE in violations:
            if _draft_echoes_customer_budget(draft_text or ""):
                violations = [v for v in violations if v != GuardrailViolation.UNVERIFIED_EXACT_PRICE]
            else:
                violations = [v for v in violations if v != GuardrailViolation.UNVERIFIED_EXACT_PRICE]
                _serious_other = frozenset(
                    {
                        GuardrailViolation.LEGAL_ADVICE,
                        GuardrailViolation.INTERNAL_ONLY_INFO,
                        GuardrailViolation.UNVERIFIED_EXACT_AVAILABILITY,
                        GuardrailViolation.PROMISE_OF_DELIVERY,
                        GuardrailViolation.UNSUPPORTED_CLAIM,
                    }
                )
                if not _serious_other.intersection(set(violations)):
                    lang_g = _policy_lang(user_message, draft_text)
                    forced_greeting_reply = (
                        "أهلاً وسهلاً! يشرفني أساعدك في اختيار عقار يناسبك. "
                        "تحب نبدأ بـ **الميزانية التقريبية** و**المنطقة** اللي في بالك؟"
                        if lang_g == "ar"
                        else (
                            "Welcome! I'm glad to help you find the right property. "
                            "Could we start with your **approximate budget** and **preferred area**?"
                        )
                    )

    policy = select_response_policy(
        customer_type=customer_type,
        routing=routing,
        intent=intent,
        requires_clarification=requires_clarification,
        is_quarantine=routing.get("quarantine", False),
    )

    decision = PolicyDecision(
        allow_response=True,
        applied_policy=policy,
        violations=violations,
    )

    # Critical violations -> block and rewrite
    if GuardrailViolation.LEGAL_ADVICE in violations:
        decision.allow_response = False
        decision.force_escalation = True
        decision.block_reason = "Legal advice detected - escalation required"
        decision.safe_rewrite = "For contract and legal matters, please speak with our legal team. I'll connect you with a specialist."
    elif GuardrailViolation.UNVERIFIED_EXACT_PRICE in violations:
        decision.rewrite_to_safe = True
        if lang == "ar":
            decision.safe_rewrite = (
                "الأسعار الدقيقة للوحدات تختلف حسب المساحة ونظام السداد، "
                "وفريقنا يزوّدك بالأرقام الرسمية عند اختيار مشروع. "
                "لو تحب نكمّل: أي **منطقة** تفضّل، وهل تفضّل **تسليم قريب** ولا **أفضل سعر للمتر**؟"
            )
        else:
            decision.safe_rewrite = (
                "Pricing varies by unit size and payment plan. Our team will provide official figures once we narrow a project. "
                "Which **area** do you prefer, and do you want **faster handover** or **best value per sqm**?"
            )
    elif GuardrailViolation.UNVERIFIED_EXACT_AVAILABILITY in violations:
        decision.rewrite_to_safe = True
        decision.safe_rewrite = (
            "التوافر يُحدَّث باستمرار — تواصل مع فريق المبيعات لآخر حالة للوحدات."
            if lang == "ar"
            else "Availability is updated regularly. Please contact our sales team for the latest unit status."
        )
    elif GuardrailViolation.PROMISE_OF_DELIVERY in violations:
        decision.rewrite_to_safe = True
        decision.safe_rewrite = (
            "مواعيد التسليم تختلف حسب المشروع والمرحلة — فريقنا يوضح الجدول المناسب لوحدتك."
            if lang == "ar"
            else "Delivery timelines are project-specific. Our team can share the schedule for your unit."
        )
    elif GuardrailViolation.INTERNAL_ONLY_INFO in violations:
        decision.allow_response = False
        decision.block_reason = "Internal information detected"
        decision.safe_rewrite = (
            "أقدر أساعدك بمعلومات عامة عن المشروع؛ للتفاصيل الدقيقة يتواصل معك الفريق."
            if lang == "ar"
            else "I can help with general project information. For specific details, please contact our team."
        )
    elif GuardrailViolation.UNSUPPORTED_CLAIM in violations:
        decision.rewrite_to_safe = True
        decision.safe_rewrite = (
            "عندنا عدة مشاريع قوية — الفريق يرشّح الأنسب حسب احتياجك."
            if lang == "ar"
            else "We have several strong projects. Our team can recommend options based on your preferences."
        )

    # Escalation mode -> escalation-required safe response
    if policy == ResponsePolicy.ESCALATION_MODE:
        decision.force_escalation = True
        decision.allow_response = True  # Allow handoff message
        if not decision.safe_rewrite and routing.get("route") == "legal_handoff":
            decision.safe_rewrite = (
                "For contract and legal matters, please speak with our legal team. "
                "I'll connect you with a specialist who can assist."
            )
        elif not decision.safe_rewrite:
            decision.safe_rewrite = (
                "طلبك يحتاج متخصص — فريقنا يكمل معاك قريباً."
                if lang == "ar"
                else "Your request requires specialist attention. Our team will follow up shortly."
            )

    # Clarification mode -> clarification-required safe response
    if policy == ResponsePolicy.CLARIFICATION_MODE:
        decision.request_clarification = True
        if not decision.safe_rewrite and not violations:
            from intelligence.services.clarification_bypass import (
                clarification_reply_hint,
                visit_scheduling_continuation,
            )

            visit_flow = visit_scheduling_continuation(conversation_history, user_message or "")
            hint = clarification_reply_hint(
                (intent.get("primary") or "") if intent else "",
                visit_flow=visit_flow,
                lang=lang,
            )
            decision.safe_rewrite = hint or (
                "لمساعدتك بدقة: ما **الميزانية التقريبية**، **المنطقة**، و**الجدول الزمني**؟"
                if lang == "ar"
                else "To better assist you, could you share more details about your requirements? (e.g. budget, location, timeline)"
            )

    # Unavailable data mode -> unavailable-data safe response
    if policy == ResponsePolicy.UNAVAILABLE_DATA_MODE:
        decision.rewrite_to_safe = True
        if not decision.safe_rewrite:
            decision.safe_rewrite = (
                "ما عنديش معلومة موثّقة لهذا السؤال تحديداً — فريق المبيعات يزوّدك بالتفاصيل الدقيقة. تحب نحدد اتصال أو معاينة؟"
                if lang == "ar"
                else (
                    "I don't have verified information for that specific question. "
                    "Our sales team can provide accurate details. Would you like to schedule a call?"
                )
            )

    # Safe answer mode (price/availability unavailable) -> unavailable-data style
    if policy == ResponsePolicy.SAFE_ANSWER_MODE and not decision.safe_rewrite:
        decision.rewrite_to_safe = True
        decision.safe_rewrite = (
            "الأسعار والتوافر يختلفان حسب الوحدة؛ فريقنا يعطيك أرقاماً دقيقة بعد ما نضيق الاختيار. "
            "تحب **مكالمة** ولا **معاينة**؟"
            if lang == "ar"
            else (
                "Pricing and availability vary by unit. Our team will provide accurate numbers for your requirements. "
                "Would you like to schedule a call or visit?"
            )
        )

    # Quarantine - no substantive response
    if policy == ResponsePolicy.QUARANTINE:
        decision.allow_response = True
        decision.safe_rewrite = (
            "شكراً لرسالتك — الفريق يتابع معاك قريباً."
            if lang == "ar"
            else "Thank you for your message. Our team will follow up shortly."
        )

    if (
        forced_greeting_reply
        and not decision.force_escalation
        and policy != ResponsePolicy.QUARANTINE
    ):
        decision.rewrite_to_safe = True
        decision.safe_rewrite = forced_greeting_reply

    return decision
