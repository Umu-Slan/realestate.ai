"""
Recommendation Eligibility - production-grade decision layer.
Recommendations appear ONLY when conversation is sufficiently qualified.
Never show projects before budget + location are known, or when market is unsupported.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

# Intents that qualify for recommendations (buy/invest focus)
RECOMMENDATION_INTENTS = frozenset({
    "property_search",
    "property_purchase",
    "price_inquiry",
    "investment_inquiry",
    "project_details",
    "location_inquiry",
    "buy_property",  # canonical
    "investment",    # canonical
})

# Location terms that indicate UNSUPPORTED markets (no Egypt inventory)
# System primarily has Egypt/Cairo-area projects
UNSUPPORTED_MARKET_INDICATORS = frozenset({
    "dubai", "دبي", "uae", "الإمارات",
    "riyadh", "الرياض", "saudi", "السعودية",
    "doha", "الدوحة", "qatar", "قطر",
    "kuwait", "الكويت", "bahrain", "البحرين",
    "oman", "عمان", "oman_country",
    "abu dhabi", "أبوظبي", "abu dhabi",
    "sharjah", "الشارقة", "ajman", "عجمان",
})


@dataclass
class RecommendationEligibility:
    """Structured decision: whether to show recommendations and why not if blocked."""
    recommendation_ready: bool = False
    recommendation_block_reason: str = ""
    missing_fields: list[str] = field(default_factory=list)
    intent_ok: bool = False
    market_supported: bool = True


def _is_location_unsupported_market(location: str) -> bool:
    """True if location indicates a market we don't have inventory for."""
    if not location or not str(location).strip():
        return False
    loc = str(location).strip().lower()
    return any(ind in loc for ind in UNSUPPORTED_MARKET_INDICATORS)


def _intent_allows_recommendation(intent_primary: str, sales_intent: str) -> bool:
    """True if intent is buy/invest focused."""
    primary = (intent_primary or "").strip().lower()
    sales = (sales_intent or "").strip().lower()
    for allowed in RECOMMENDATION_INTENTS:
        if allowed in primary or allowed in sales:
            return True
    # Catch common Arabic/English variations
    if any(x in primary for x in ["شقة", "فيلا", "شراء", "استثمار", "عايز", "أريد", "property", "buy", "investment"]):
        return True
    return False


def check_recommendation_eligibility(
    *,
    intent_primary: str = "",
    sales_intent: str = "",
    budget_min: Optional[Decimal] = None,
    budget_max: Optional[Decimal] = None,
    location_preference: str = "",
    property_type: str = "",
    response_mode: str = "",
) -> RecommendationEligibility:
    """
    Decide if recommendations should be shown.
    Returns RecommendationEligibility with recommendation_ready and block_reason.
    """
    missing: list[str] = []
    if not (budget_min is not None or budget_max is not None):
        missing.append("budget")
    if not (location_preference or "").strip():
        missing.append("location")

    # Support mode: no property recommendations
    if response_mode == "support":
        return RecommendationEligibility(
            recommendation_ready=False,
            recommendation_block_reason="support_mode",
            missing_fields=missing,
            intent_ok=False,
            market_supported=True,
        )

    intent_ok = _intent_allows_recommendation(intent_primary, sales_intent)
    if not intent_ok:
        return RecommendationEligibility(
            recommendation_ready=False,
            recommendation_block_reason="intent_not_buy",
            missing_fields=missing,
            intent_ok=False,
            market_supported=True,
        )

    if "budget" in missing:
        return RecommendationEligibility(
            recommendation_ready=False,
            recommendation_block_reason="budget_missing",
            missing_fields=missing,
            intent_ok=True,
            market_supported=True,
        )

    if "location" in missing:
        return RecommendationEligibility(
            recommendation_ready=False,
            recommendation_block_reason="location_missing",
            missing_fields=missing,
            intent_ok=True,
            market_supported=True,
        )

    # Check market support
    if _is_location_unsupported_market(location_preference):
        return RecommendationEligibility(
            recommendation_ready=False,
            recommendation_block_reason="unsupported_market",
            missing_fields=[],
            intent_ok=True,
            market_supported=False,
        )

    return RecommendationEligibility(
        recommendation_ready=True,
        recommendation_block_reason="",
        missing_fields=[],
        intent_ok=True,
        market_supported=True,
    )
