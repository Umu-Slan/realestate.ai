"""
Tests for recommendation eligibility.
Verifies: budget+location required, intent must be buy/invest, unsupported markets blocked.
"""
import pytest
from decimal import Decimal

from orchestration.recommendation_eligibility import (
    check_recommendation_eligibility,
    UNSUPPORTED_MARKET_INDICATORS,
)


def test_eligibility_ready_when_budget_location_intent_ok():
    """Ready when budget, location, and buy/invest intent."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="New Cairo",
    )
    assert e.recommendation_ready is True
    assert e.recommendation_block_reason == ""


def test_eligibility_blocked_budget_missing():
    """Blocked when budget not provided."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=None,
        budget_max=None,
        location_preference="معادي",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "budget_missing"


def test_eligibility_blocked_location_missing():
    """Blocked when location not provided."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "location_missing"


def test_eligibility_blocked_unsupported_market_dubai():
    """Blocked when location indicates Dubai/UAE (no Egypt inventory)."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="Dubai",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "unsupported_market"


def test_eligibility_blocked_unsupported_market_riyadh():
    """Blocked when location indicates Riyadh (Saudi)."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="الرياض",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "unsupported_market"


def test_eligibility_blocked_support_mode():
    """Blocked when response_mode is support."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="New Cairo",
        response_mode="support",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "support_mode"


def test_eligibility_blocked_intent_not_buy():
    """Blocked when intent is not buy/invest focused."""
    e = check_recommendation_eligibility(
        intent_primary="support_complaint",
        sales_intent="support_request",
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="New Cairo",
    )
    assert e.recommendation_ready is False
    assert e.recommendation_block_reason == "intent_not_buy"


def test_eligibility_budget_max_only_accepted():
    """Budget max alone is sufficient (budget range known)."""
    e = check_recommendation_eligibility(
        intent_primary="property_purchase",
        sales_intent="property_search",
        budget_min=None,
        budget_max=Decimal("5000000"),
        location_preference="المعادي",
    )
    assert e.recommendation_ready is True
