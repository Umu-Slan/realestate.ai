"""
Memory merge logic - convert intent/qualification into facts and merge into profile.
Explicit facts from user message get higher strength; inferred get lower.
"""
from decimal import Decimal
from typing import Any, Optional

from orchestration.agents.memory_schema import CustomerMemoryProfile, MEMORY_FIELDS


def _strength_for_explicit(confidence: float) -> str:
    """Map confidence to strength for explicit facts."""
    if confidence >= 0.8:
        return "strong"
    if confidence >= 0.5:
        return "medium"
    return "weak"


def _strength_for_inferred(confidence: float) -> str:
    """Map confidence to strength for inferred facts."""
    if confidence >= 0.7:
        return "medium"
    return "weak"


def facts_from_intent_entities(entities: dict, confidence: float = 0.75) -> list[tuple[str, Any, str, str]]:
    """
    Convert intent detector entities to (field, value, strength, source) tuples.
    Intent entities are typically explicit (user said them).
    """
    facts = []
    if not entities:
        return facts
    strength = _strength_for_explicit(confidence)
    source = "explicit"
    if entities.get("budget"):
        b = entities["budget"]
        if isinstance(b, dict):
            facts.append(("budget", {"min": b.get("min"), "max": b.get("max")}, strength, source))
    if entities.get("location"):
        loc = entities["location"]
        if loc:
            facts.append(("preferred_locations", [loc] if isinstance(loc, str) else loc, strength, source))
    if entities.get("property_type"):
        facts.append(("property_type", entities["property_type"], strength, source))
    if entities.get("bedrooms") is not None:
        facts.append(("bedrooms", int(entities["bedrooms"]), strength, source))
    if entities.get("timeline"):
        facts.append(("timeline", entities["timeline"], strength, source))
    if entities.get("investment_vs_residence"):
        facts.append(("investment_vs_residence", entities["investment_vs_residence"], strength, source))
    return facts


def facts_from_qualification(
    qualification: dict,
    confidence: str = "unknown",
) -> list[tuple[str, Any, str, str]]:
    """
    Convert qualification extractor output to facts.
    Qualification can be explicit (user said) or inferred (LLM derived).
    """
    facts = []
    if not qualification:
        return facts
    conf = 0.6 if confidence == "high" else 0.4 if confidence == "medium" else 0.3
    strength_explicit = _strength_for_explicit(conf)
    strength_inferred = _strength_for_inferred(conf)

    if qualification.get("budget_min") is not None or qualification.get("budget_max") is not None:
        bmin = qualification.get("budget_min")
        bmax = qualification.get("budget_max")
        if bmin is not None or bmax is not None:
            try:
                d = {}
                if bmin is not None:
                    d["min"] = float(Decimal(str(bmin)))
                if bmax is not None:
                    d["max"] = float(Decimal(str(bmax)))
                if d:
                    facts.append(("budget", d, strength_explicit, "explicit"))
            except Exception:
                pass
    if qualification.get("location_preference"):
        facts.append(
            (
                "preferred_locations",
                [qualification["location_preference"].strip()],
                strength_explicit,
                "explicit",
            )
        )
    if qualification.get("property_type"):
        facts.append(("property_type", qualification["property_type"].strip(), strength_explicit, "explicit"))
    if qualification.get("purpose"):  # residence vs investment
        facts.append(("investment_vs_residence", qualification["purpose"].strip(), strength_explicit, "explicit"))
    if qualification.get("urgency"):
        facts.append(("urgency", qualification["urgency"].strip(), strength_inferred, "inferred"))
    if qualification.get("timeline") or qualification.get("urgency"):
        tl = qualification.get("timeline") or qualification.get("urgency", "")
        if tl:
            facts.append(("timeline", str(tl).strip(), strength_inferred, "inferred"))
    return facts


def detect_rejected_options(message: str) -> list[str]:
    """
    Simple heuristic: "لا"، "مش عايز"، "مش مناسب" + project/area name.
    Returns list of rejected option strings.
    """
    t = (message or "").lower().strip()
    rejected = []
    # Patterns: "مش عايز X", "لا X", "X مش مناسب", "مرفوض X"
    reject_prefixes = ["لا", "مش عايز", "لا أريد", "مرفوض", "لا يعجبني", "not interested", "no"]
    for prefix in reject_prefixes:
        if prefix in t:
            # Extract what follows - simplified
            idx = t.find(prefix)
            rest = t[idx + len(prefix):].strip()
            words = rest.split()[:5]
            if words:
                candidate = " ".join(w for w in words if len(w) > 1)[:80]
                if candidate and len(candidate) > 2:
                    rejected.append(candidate.strip())
    return rejected[:5]


def detect_financing_preference(message: str) -> Optional[str]:
    """Detect financing style: تقسيط، كاش، cash, installment."""
    t = (message or "").lower()
    if any(w in t for w in ["تقسيط", "installment", "أقساط", "قسط"]):
        return "installment"
    if any(w in t for w in ["كاش", "cash", "نقدي", "دفعة واحدة"]):
        return "cash"
    return None


def merge_into_profile(
    profile: CustomerMemoryProfile,
    intent_entities: dict,
    qualification: dict,
    message_text: str,
    intent_confidence: float = 0.75,
    qualification_confidence: str = "unknown",
) -> int:
    """
    Merge new facts from intent and qualification into profile.
    Returns count of fields updated.
    """
    updated = 0
    for field, value, strength, source in facts_from_intent_entities(
        intent_entities or {}, intent_confidence
    ):
        if profile.set_fact(field, value, strength=strength, source=source):
            updated += 1
    for field, value, strength, source in facts_from_qualification(
        qualification or {}, qualification_confidence
    ):
        if profile.set_fact(field, value, strength=strength, source=source):
            updated += 1
    for loc in detect_rejected_options(message_text):
        if profile.set_fact("rejected_options", [loc], strength="weak", source="inferred", merge=True):
            updated += 1
    fin = detect_financing_preference(message_text)
    if fin and profile.set_fact("preferred_financing_style", fin, strength="strong", source="explicit"):
        updated += 1
    return updated
