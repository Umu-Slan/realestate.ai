"""
Arabic input normalization for the sales system.
Handles Egyptian, Gulf, short/vague, typo-heavy, and mixed Arabic/English.
Outputs canonical forms for intent/objection detection while preserving user voice for LLM context.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ArabicNormalizationResult:
    """Result of normalizing Arabic input."""
    normalized: str
    dialect_hint: str  # "egyptian" | "gulf" | "mixed" | "standard"
    is_vague: bool
    expansion_hints: list[str]
    original: str


# Egyptian → canonical mappings (for detection; we preserve original for display)
EGYPTIAN_CANONICAL = {
    "عايز": "أريد",
    "عاوز": "أريد",
    "عاوزه": "أريد",
    "عايزة": "أريد",
    "ابغى": "أريد",
    "ابي": "أريد",
    "حابب": "أريد",
    "محتاج": "أحتاج",
    "معايا": "لدي",
    "معاي": "لدي",
    "كام": "كم",
    "امتى": "متى",
    "فين": "أين",
    "ازاي": "كيف",
    "عشان": "لأن",
    "بس": "فقط",
    "يس": "نعم",
    "ايوه": "نعم",
    "اه": "نعم",
    "لالا": "لا",
    "مش": "ليس",
    "مفيش": "لا يوجد",
    "هستنى": "سأنتظر",
    "استنى": "انتظر",
    "مش عارف": "لست متأكد",
    "مش متأكد": "لست متأكد",
}

# Common Arabic typos (chars often confused)
TYPO_CORRECTIONS = {
    "شقه": "شقة",
    "شقا": "شقة",
    "غاليه": "غالية",
    "غاليه جدا": "غالية جداً",
    "مليو": "مليون",
    "مليان": "مليون",
    "ميزانتي": "ميزانيتي",
    "ميزانيه": "ميزانية",
    "المنطقه": "المنطقة",
    "اسعار": "أسعار",
    "اسعر": "أسعار",
    "مقارنه": "مقارنة",
}

# Gulf dialect markers
GULF_MARKERS = ["ابغى", "ابي", "عطني", "وين", "شلون", "ليش", "مره", "زين", "طيب"]

# Short/vague patterns
VAGUE_PATTERNS = [
    (r"^(hi|hello|مرحبا|اهلا|هلا|الو)\s*$", ["greeting"]),
    (r"^(عايز|ابغى|اريد|اريد)\s*$", ["incomplete_want"]),
    (r"^(\d+\s*مليون?|مليون)\s*$", ["budget_only"]),
    (r"^(شي)\s*$", ["very_vague"]),
    (r"^\.{2,}$", ["ellipsis"]),
    (r"^[?\?؟]{1,3}$", ["question_only"]),
]


def _apply_typo_corrections(text: str) -> str:
    """Apply common typo corrections for Arabic words."""
    result = text
    for wrong, correct in TYPO_CORRECTIONS.items():
        if wrong in result:
            result = result.replace(wrong, correct)
    return result


def _detect_dialect(text: str) -> str:
    """Detect primary dialect from text."""
    t = text.strip().lower()
    if any(m in t for m in GULF_MARKERS):
        return "gulf"
    egyptian_markers = ["عايز", "عاوز", "معايا", "امتى", "فين", "يس", "ايوه", "مش", "هستنى"]
    if any(m in t for m in egyptian_markers):
        return "egyptian"
    ar_count = sum(1 for c in t if "\u0600" <= c <= "\u06FF")
    en_count = sum(1 for c in t if c.isalpha() and ord(c) < 128)
    if ar_count > 0 and en_count > ar_count * 0.3:
        return "mixed"
    return "standard"


def _is_vague(text: str) -> tuple[bool, list[str]]:
    """Check if input is short/vague and return expansion hints."""
    t = (text or "").strip()
    if len(t) < 4:
        return True, ["very_short", "ask_clarification"]
    for pattern, hints in VAGUE_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return True, hints
    if len(t) < 15 and not any(c.isdigit() for c in t):
        return True, ["possibly_vague"]
    return False, []


def normalize_arabic_input(raw: str) -> ArabicNormalizationResult:
    """
    Normalize Arabic input for consistent downstream processing.
    Returns canonical form for detection while preserving semantics.
    """
    if not raw or not isinstance(raw, str):
        return ArabicNormalizationResult(
            normalized="",
            dialect_hint="standard",
            is_vague=True,
            expansion_hints=["empty"],
            original=raw or "",
        )

    text = raw.strip()
    if not text:
        return ArabicNormalizationResult(
            normalized="",
            dialect_hint="standard",
            is_vague=True,
            expansion_hints=["empty"],
            original=raw,
        )

    # Apply typo corrections
    normalized = _apply_typo_corrections(text)

    # Normalize multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # For detection: optionally map Egyptian/Gulf to canonical (we keep original for LLM)
    # We pass normalized through - typo fixes help; dialect mapping can be done in detection
    dialect = _detect_dialect(normalized)
    is_vague, hints = _is_vague(normalized)

    return ArabicNormalizationResult(
        normalized=normalized,
        dialect_hint=dialect,
        is_vague=is_vague,
        expansion_hints=hints,
        original=raw,
    )


def normalize_for_detection(text: str) -> str:
    """
    Return text optimized for intent/objection detection.
    Applies typo fixes and optional canonical mappings.
    """
    result = normalize_arabic_input(text)
    t = result.normalized.lower()
    # Map key Egyptian/Gulf verbs for detection (intent, objection)
    for egypt, canonical in EGYPTIAN_CANONICAL.items():
        if egypt in t:
            t = t.replace(egypt, canonical)
    return t.strip() or result.normalized
