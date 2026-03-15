"""
Customer-facing CTA mapping. Never expose internal strategy labels or debug text.
Used by sales_chat, conversation_history, and orchestration.service for persistence.
"""
from typing import Optional

# Human-readable CTA labels for next_step (never expose internal identifiers or reason text)
NEXT_STEP_LABELS = {
    "ask_budget": {"label": "ما الميزانية المناسبة لك؟", "action": "ميزانيتي حوالي"},
    "ask_location": {"label": "في أي منطقة تفضل السكن؟", "action": "أفضل منطقة"},
    "ask_preferred_area": {"label": "في أي منطقة تفضل السكن؟", "action": "أفضل منطقة"},
    "ask_property_type": {"label": "هل تبحث عن شقة أم فيلا؟", "action": "عايز شقة"},
    "ask_bedrooms": {"label": "كم غرفة نوم تحتاج؟", "action": "أحتاج غرفتين"},
    "recommend_projects": {"label": "عرض المشاريع المناسبة", "action": "عرض المشاريع المناسبة"},
    "recommend_project": {"label": "عرض المشاريع المناسبة", "action": "عرض المشاريع المناسبة"},
    "propose_visit": {"label": "حجز معاينة", "action": "أريد حجز معاينة"},
    "send_brochure": {"label": "إرسال بروشور", "action": "أريد بروشور"},
    "nurture": {"label": "استمر في المحادثة", "action": ""},
    "move_to_human": {"label": "التحدث مع موظف", "action": "أريد التحدث مع موظف"},
    "address_objection": {"label": "توضيح إضافي", "action": ""},
}


def to_customer_facing_next_step(raw: Optional[str]) -> Optional[dict]:
    """Convert internal next_step to customer-facing {label, action}. Never expose action:reason or internal IDs."""
    from engines.response_sanitizer import is_internal_objective

    raw = (raw or "").strip()
    if is_internal_objective(raw):
        return None
    action_key = raw.split(":")[0].strip().lower() if ":" in raw else raw.lower()
    mapped = NEXT_STEP_LABELS.get(action_key)
    if mapped:
        return mapped
    mapped = NEXT_STEP_LABELS.get(raw.lower())
    if mapped:
        return mapped
    if raw and len(raw) < 60 and not is_internal_objective(raw) and ":" not in raw:
        return {"label": raw, "action": raw}
    return None
