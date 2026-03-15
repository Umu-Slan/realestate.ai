"""
Tests for production Recommendation Agent.
Covers: top_recommendations, why_it_matches, tradeoffs, recommendation_confidence,
alternatives when fit is weak, persistence flow.
"""
import pytest
from unittest.mock import MagicMock

from orchestration.agents.recommendation_agent import (
    RecommendationAgent,
    _to_top_recommendation,
)
from orchestration.agents.schemas import RecommendationAgentOutput, WEAK_FIT_THRESHOLD
from orchestration.agents.base import AgentContext


def test_to_top_recommendation_adds_why_and_tradeoffs():
    m = {
        "project_id": 1,
        "project_name": "Towers",
        "match_reasons": ["budget_fit", "location_match"],
        "rationale": "Fits your budget",
        "trade_offs": ["pricing_unverified"],
    }
    out = _to_top_recommendation(m)
    assert out["why_it_matches"] == ["budget_fit", "location_match", "Fits your budget"]
    assert out["tradeoffs"] == ["pricing_unverified"]


def test_to_top_recommendation_uses_top_reasons_fallback():
    m = {"project_id": 2, "top_reasons": ["location_match"], "tradeoffs": ["different_area"]}
    out = _to_top_recommendation(m)
    assert "location_match" in out["why_it_matches"]
    assert out["tradeoffs"] == ["different_area"]


def test_recommendation_agent_blocks_when_not_qualified():
    """No recommendations when budget or location missing (eligibility blocks)."""
    ctx = MagicMock(spec=AgentContext)
    ctx.get_qualification.return_value = {"budget_min": None, "location_preference": ""}
    ctx.intent_output = {"primary": "property_purchase", "sales_intent": "property_search"}
    ctx.response_mode = "sales"
    ctx.property_matching_output = None
    ctx.recommendation_output = None

    agent = RecommendationAgent()
    result = agent.run(ctx)

    assert result.success
    out = ctx.recommendation_output
    assert out["recommendation_ready"] is False
    assert out["recommendation_block_reason"] in ("budget_missing", "location_missing")
    assert out["top_recommendations"] == []


def test_recommendation_agent_blocks_unsupported_market():
    """No recommendations when location is Dubai/UAE (unsupported market)."""
    from decimal import Decimal

    ctx = MagicMock(spec=AgentContext)
    ctx.get_qualification.return_value = {
        "budget_min": Decimal("2000000"),
        "budget_max": Decimal("3000000"),
        "location_preference": "Dubai",
    }
    ctx.intent_output = {"primary": "property_purchase", "sales_intent": "property_search"}
    ctx.response_mode = "sales"
    ctx.property_matching_output = None

    agent = RecommendationAgent()
    result = agent.run(ctx)

    assert result.success
    out = ctx.recommendation_output
    assert out["recommendation_ready"] is False
    assert out["recommendation_block_reason"] == "unsupported_market"
    assert out["top_recommendations"] == []


def test_recommendation_agent_uses_property_matching_output():
    """When property_matching has matches and qualified, recommendation reuses them."""
    from decimal import Decimal

    ctx = MagicMock(spec=AgentContext)
    ctx.get_qualification.return_value = {
        "budget_min": Decimal("2000000"),
        "budget_max": Decimal("3000000"),
        "location_preference": "New Cairo",
    }
    ctx.intent_output = {"primary": "property_purchase", "sales_intent": "property_search"}
    ctx.response_mode = "sales"
    ctx.property_matching_output = {
        "matches": [
            {
                "project_id": 1,
                "project_name": "Project A",
                "location": "New Cairo",
                "rationale": "Fits budget",
                "match_reasons": ["budget_fit"],
                "trade_offs": [],
                "fit_score": 0.85,
                "confidence": 0.8,
                "has_verified_pricing": True,
            },
        ],
        "alternatives": [{"project_id": 2, "project_name": "B", "rationale": "Nearby"}],
        "qualification_summary": "Budget 2M",
        "data_completeness": "full",
        "overall_confidence": 0.85,
    }
    ctx.lang = "ar"
    ctx.market_context_output = None

    agent = RecommendationAgent()
    result = agent.run(ctx)

    assert result.success
    assert ctx.recommendation_output
    out = ctx.recommendation_output
    assert out["recommendation_ready"] is True
    assert "top_recommendations" in out
    assert len(out["top_recommendations"]) == 1
    assert out["top_recommendations"][0]["project_name"] == "Project A"
    assert "why_it_matches" in out["top_recommendations"][0]
    assert "budget_fit" in out["top_recommendations"][0]["why_it_matches"]
    assert out["recommendation_confidence"] == 0.85
    assert out["response_text"]


def test_recommendation_agent_surfaces_more_alternatives_when_fit_weak():
    """Weak fit (score < threshold) surfaces more alternatives."""
    from decimal import Decimal

    ctx = MagicMock(spec=AgentContext)
    ctx.get_qualification.return_value = {
        "budget_min": Decimal("2000000"),
        "budget_max": Decimal("3000000"),
        "location_preference": "6 October",
    }
    ctx.intent_output = {"primary": "property_search", "sales_intent": "property_search"}
    ctx.response_mode = "sales"
    ctx.property_matching_output = {
        "matches": [
            {
                "project_id": 1,
                "project_name": "A",
                "fit_score": 0.4,
                "match_reasons": ["location_nearby"],
                "trade_offs": ["different_area"],
                "rationale": "Near match",
            },
        ],
        "alternatives": [
            {"project_id": 2, "project_name": "B", "rationale": "Alt 1"},
            {"project_id": 3, "project_name": "C", "rationale": "Alt 2"},
            {"project_id": 4, "project_name": "D", "rationale": "Alt 3"},
            {"project_id": 5, "project_name": "E", "rationale": "Alt 4"},
            {"project_id": 6, "project_name": "F", "rationale": "Alt 5"},
        ],
        "qualification_summary": "",
        "data_completeness": "partial",
        "overall_confidence": 0.4,
    }
    ctx.lang = "ar"
    ctx.market_context_output = None

    agent = RecommendationAgent()
    result = agent.run(ctx)

    assert result.success
    out = ctx.recommendation_output
    assert out["recommendation_ready"] is True
    assert len(out["alternatives"]) == 5
    assert out["top_recommendations"][0]["fit_score"] == 0.4


def test_recommendation_output_roundtrip():
    """RecommendationAgentOutput round-trip with new fields."""
    o = RecommendationAgentOutput(
        matches=[{"project_id": 1, "project_name": "X", "why_it_matches": ["a"], "tradeoffs": ["b"]}],
        top_recommendations=[{"project_id": 1, "why_it_matches": ["a"], "tradeoffs": ["b"]}],
        alternatives=[],
        qualification_summary="Test",
        recommendation_confidence=0.7,
        response_text="Response",
        recommendation_ready=True,
        recommendation_block_reason="",
    )
    d = o.to_dict()
    assert d["recommendation_confidence"] == 0.7
    assert d["recommendation_ready"] is True
    assert d["top_recommendations"]
    restored = RecommendationAgentOutput.from_dict(d)
    assert restored.recommendation_confidence == 0.7
    assert restored.recommendation_ready is True
    assert len(restored.top_recommendations) == 1
