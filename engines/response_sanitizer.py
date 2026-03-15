"""
Response sanitizer - strips internal strategy/objective text from customer-facing replies.
Ensures end users NEVER see system labels, debug text, or placeholder objectives.
"""
import re
from typing import Optional

# Internal phrases that must NEVER appear in customer-facing responses
# (from journey_stage_agent, conversation_plan, strategy, fallbacks)
INTERNAL_PHRASES = [
    r"Share value proposition and qualify budget",
    r"qualify budget/location",
    r"Gather project preference",
    r"Offer property overviews and narrow preferences",
    r"Send project details and schedule visit",
    r"Share brochures and arrange site visit",
    r"Confirm visit slot and send directions",
    r"Present offers and facilitate decision",
    r"Guide through booking steps",
    r"Follow up on handover",
    r"Resolve issue and maintain relationship",
    r"Continue qualification and nurture",
    r"Qualify and nurture lead",
    r"Address concern directly, then suggest",
    r"Offer resolution and next steps",
    r"Share value/insight",
    r"Share helpful content and ask preferences",
    r"Connect customer with sales rep",
    r"Present matching projects",
    r"Suggest site visit to view the unit",
    r"Clarify availability and next step",
    r"Address objection then suggest",
    r"Internal objective",
    r"Best next move:",
    r"Current objective:",
    r"sales_objective",
    r"next_sales_move",
    r"recommended_cta",
]


def sanitize_customer_response(text: Optional[str]) -> str:
    """
    Remove internal strategy/objective phrases from response.
    Returns cleaned text safe for customer display.
    """
    if not text or not isinstance(text, str):
        return text or ""
    out = text.strip()
    for phrase in INTERNAL_PHRASES:
        # Case-insensitive, allow word boundaries
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        out = pattern.sub("", out)
    # Collapse multiple spaces/newlines
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"^\s*[:\-]\s*", "", out)  # trim leading ": " or "- "
    return out.strip()


def is_internal_objective(text: Optional[str]) -> bool:
    """Return True if text looks like internal strategy/objective (should not be shown to users)."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip().lower()
    # Internal patterns: English strategy labels, imperative verbs for internal use
    internal_markers = [
        "share value proposition",
        "qualify budget",
        "gather project",
        "offer property overviews",
        "send project details",
        "share brochures",
        "confirm visit slot",
        "present offers",
        "guide through booking",
        "continue qualification",
        "resolve issue and maintain",
        "address concern directly",
        "offer resolution and next",
    ]
    return any(m in t for m in internal_markers)
