"""
Graceful failure handling and safe fallbacks for v0 pilot.
Centralized recovery messages and degradation modes.
"""
from typing import Optional

# --- Safe fallback messages (Egypt-first, bilingual) ---

FALLBACK_MISSING_KNOWLEDGE = (
    "أعتذر، لا أستطيع العثور على معلومات كافية حول هذا الموضوع حاليًا. "
    "يرجى التواصل مع فريقنا للحصول على تفاصيل دقيقة."
)

FALLBACK_STALE_KNOWLEDGE = (
    "المعلومات قد تكون محدثة. يرجى التواصل مع فريق المبيعات للتأكد من أحدث التفاصيل والأسعار."
)

FALLBACK_STRUCTURED_UNAVAILABLE = (
    "البيانات التنظيمية غير متاحة مؤقتاً. يرجى المحاولة لاحقاً أو التواصل معنا مباشرة."
)

FALLBACK_LLM_TIMEOUT = (
    "أعتذر، واجهت صعوبة في معالجة طلبك. يرجى المحاولة مرة أخرى أو التواصل مع فريقنا."
)

FALLBACK_CRM_IMPORT_ERROR = (
    "حدث خطأ أثناء استيراد الملف. يرجى التحقق من صيغة الملف والمحاولة مرة أخرى."
)

FALLBACK_AMBIGUOUS_IDENTITY = (
    "للتأكد من هويتك، يرجى تقديم رقم الهاتف أو البريد الإلكتروني."
)

FALLBACK_LOW_CONFIDENCE = (
    "لم أفهم بشكل كامل. هل يمكنك توضيح ما تبحث عنه بالتحديد؟"
)

FALLBACK_CONTRADICTORY_QUALIFICATION = (
    "يبدو أن هناك تناقضاً في المعلومات. يرجى التأكد من الميزانية والتفاصيل ثم إعادة المحاولة."
)

FALLBACK_GENERIC = (
    "عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو التواصل معنا."
)


def get_fallback_for(failure_type: str, lang: str = "ar") -> str:
    """
    Return safe fallback message for failure type.
    failure_type: missing_knowledge | stale_knowledge | structured_unavailable |
                  llm_timeout | crm_import_error | ambiguous_identity |
                  low_confidence_intent | low_confidence_scoring |
                  contradictory_qualification | generic
    """
    mapping = {
        "missing_knowledge": FALLBACK_MISSING_KNOWLEDGE,
        "stale_knowledge": FALLBACK_STALE_KNOWLEDGE,
        "structured_unavailable": FALLBACK_STRUCTURED_UNAVAILABLE,
        "llm_timeout": FALLBACK_LLM_TIMEOUT,
        "crm_import_error": FALLBACK_CRM_IMPORT_ERROR,
        "ambiguous_identity": FALLBACK_AMBIGUOUS_IDENTITY,
        "low_confidence_intent": FALLBACK_LOW_CONFIDENCE,
        "low_confidence_scoring": FALLBACK_LOW_CONFIDENCE,
        "contradictory_qualification": FALLBACK_CONTRADICTORY_QUALIFICATION,
    }
    return mapping.get(failure_type, FALLBACK_GENERIC)


def detect_contradictory_qualification(
    budget_min: Optional[float], budget_max: Optional[float]
) -> bool:
    """Check if budget_min > budget_max (contradiction)."""
    if budget_min is None or budget_max is None:
        return False
    return float(budget_min) > float(budget_max)
