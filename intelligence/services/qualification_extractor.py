"""
Lead qualification extraction - LLM-assisted.
Extracts budget, location, project, property type, timeline, etc.
"""
import re
from decimal import Decimal
from typing import Optional

from intelligence.schemas import QualificationExtraction
from intelligence.llm_client import call_llm


def _parse_amount(s: str) -> Optional[Decimal]:
    """Extract numeric amount from string (EGP, مليون, etc.)."""
    if not s:
        return None
    s = s.replace(",", "").replace(" ", "")
    # Handle Arabic numerals
    arabic = "٠١٢٣٤٥٦٧٨٩"
    for i, a in enumerate(arabic):
        s = s.replace(a, str(i))
    m = re.search(r"[\d.]+", s)
    if not m:
        return None
    try:
        val = Decimal(m.group())
        if "مليون" in s or "million" in s.lower():
            val *= 1_000_000
        elif "ألف" in s or "الف" in s or "k" in s.lower():
            val *= 1_000
        return val
    except Exception:
        return None


def _deterministic_extract(text: str) -> QualificationExtraction:
    """Fallback extraction using regex."""
    t = (text or "").strip()
    q = QualificationExtraction(confidence="low")

    # Budget patterns: 2 million, مليونين، 500 ألف، 1.5M
    budget_pat = r"(?:حوالي|about|تقريباً|approximately)?\s*(\d+(?:\.\d+)?)\s*(?:مليون|million|مليونين|ألف|الف|k|m)"
    if m := re.search(budget_pat, t, re.IGNORECASE | re.UNICODE):
        amt = _parse_amount(m.group(0))
        if amt:
            q.budget_min = amt * Decimal("0.8")
            q.budget_max = amt * Decimal("1.2")
            q.budget_clarity = "approximate"

    # Location: في المعادي، في اكتوبر، New Cairo, in New Cairo
    loc_pat = r"(?:في|فيين|location|منطقة|in)\s+([^\s,،.]+(?:\s+[^\s,،.]+)?)"
    if m := re.search(loc_pat, t, re.IGNORECASE | re.UNICODE):
        q.location_preference = m.group(1).strip()

    # Project: مشروع X
    proj_pat = r"(?:مشروع|project)\s+([^\s,،.]+)"
    if m := re.search(proj_pat, t, re.IGNORECASE | re.UNICODE):
        q.project_preference = m.group(1).strip()

    # Property type: شقة، فيلا، استوديو
    type_words = ["شقة", "فيلا", "استوديو", "دوبلكس", " apartment", "villa", "studio", "duplex", "تاون هاوس"]
    for w in type_words:
        if w in t.lower():
            q.property_type = w.strip()
            break

    # Timeline
    if any(x in t for x in ["فوراً", "قريب", "أسبوع", "شهر", "now", "soon", "أسرع"]):
        q.urgency = "immediate"
        q.purchase_timeline = "within 1 month"
    elif any(x in t for x in ["شهور", "سنة", "عام", "months", "year"]):
        q.urgency = "exploring"
        q.purchase_timeline = "3-12 months"

    # Residence vs investment
    if any(x in t for x in ["استثمار", "investment", "استثماري"]):
        q.residence_vs_investment = "investment"
    elif any(x in t for x in ["سكن", "residence", "للعائلة"]):
        q.residence_vs_investment = "residence"

    # Missing fields
    missing = []
    if not q.budget_min and not q.budget_max:
        missing.append("budget")
    if not q.location_preference:
        missing.append("location")
    if not q.project_preference:
        missing.append("project")
    if not q.property_type:
        missing.append("property_type")
    if not q.purchase_timeline:
        missing.append("timeline")
    q.missing_fields = missing

    return q


def extract_qualification(
    message_text: str,
    conversation_history: list[dict] | None = None,
    use_llm: bool = True,
) -> QualificationExtraction:
    """
    Extract lead qualification from message.
    Returns budget, location, project, type, timeline, etc.
    """
    text = (message_text or "").strip()
    if not text:
        return QualificationExtraction(confidence="unknown", missing_fields=["budget", "location", "project", "property_type", "timeline"])

    if use_llm:
        result = _llm_extract(text, conversation_history or [])
        if result:
            return result

    return _deterministic_extract(text)


def _llm_extract(text: str, history: list[dict]) -> QualificationExtraction | None:
    """LLM-based extraction."""
    history_str = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')[:150]}" for m in history[-5:]
    ) if history else ""

    system = """You extract lead qualification from Egyptian real estate conversations.
Return JSON with: budget_min (number), budget_max (number), budget_clarity (explicit_range|approximate|none|unclear),
location_preference, project_preference, property_type, residence_vs_investment (residence|investment|both|unknown),
payment_method (cash|installments|both|unknown), purchase_timeline, financing_readiness (ready|exploring|not_ready|unknown),
family_size (number or null), urgency (immediate|soon|exploring|unknown),
missing_fields (list of field names not yet provided), confidence (high|medium|low|unknown).
Use empty string or null for unknown. Budget in EGP."""

    user = f"Context:\n{history_str}\n\nUser: {text}" if history_str else f"User: {text}"

    out = call_llm(system, user)
    if not out:
        return None

    q = QualificationExtraction(
        budget_min=Decimal(str(out["budget_min"])) if out.get("budget_min") else None,
        budget_max=Decimal(str(out["budget_max"])) if out.get("budget_max") else None,
        budget_clarity=out.get("budget_clarity", ""),
        location_preference=out.get("location_preference", "") or "",
        project_preference=out.get("project_preference", "") or "",
        property_type=out.get("property_type", "") or "",
        residence_vs_investment=out.get("residence_vs_investment", "") or "",
        payment_method=out.get("payment_method", "") or "",
        purchase_timeline=out.get("purchase_timeline", "") or "",
        financing_readiness=out.get("financing_readiness", "") or "",
        family_size=int(out["family_size"]) if out.get("family_size") is not None else None,
        urgency=out.get("urgency", "") or "",
        missing_fields=out.get("missing_fields", []) or [],
        confidence=out.get("confidence", "unknown"),
    )
    return q
