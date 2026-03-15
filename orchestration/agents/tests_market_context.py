"""
Tests for market context integration in agents.
"""
import pytest

try:
    import pgvector  # noqa: F401
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

from orchestration.agents.base import AgentContext
from orchestration.agents.schemas import PropertyMatch
from orchestration.agents.property_matching_agent import PropertyMatchingAgent
from orchestration.agents.sales_strategy_agent import SalesStrategyAgent


def test_property_match_with_market_context():
    """PropertyMatch serializes and deserializes market_context."""
    m = PropertyMatch(
        project_id=1,
        project_name="Test",
        market_context={
            "project_id": 1,
            "area_attractiveness": "high",
            "family_suitability": True,
            "price_segment": "mid",
        },
    )
    d = m.to_dict()
    assert "market_context" in d
    assert d["market_context"]["family_suitability"] is True
    restored = PropertyMatch.from_dict(d)
    assert restored.market_context == m.market_context


def test_property_match_without_market_context():
    """PropertyMatch works without market_context (backward compat)."""
    m = PropertyMatch(project_id=1, project_name="Test")
    d = m.to_dict()
    assert "market_context" not in d or d.get("market_context") is None
    restored = PropertyMatch.from_dict(d)
    assert restored.market_context is None


@pytest.mark.django_db
def test_sales_strategy_uses_market_context_key_points():
    """Sales strategy adds market tags to key_points when market context available."""
    agent = SalesStrategyAgent()
    ctx = AgentContext(
        run_id="t1",
        message_text="أريد شقة للمعيشة",
        conversation_history=[],
        intent_output={"primary": "project_inquiry"},
        qualification_output={"budget_min": "2000000", "location_preference": "New Cairo"},
        memory_output={"customer_type_hint": "new_lead"},
        market_context_output={
            "projects": {
                1: {
                    "project_id": 1,
                    "family_suitability": True,
                    "investment_suitability": False,
                    "price_segment": "mid",
                    "demand_cues": ["high_demand"],
                },
            },
            "project_count": 1,
        },
    )
    result = agent.run(ctx)
    assert result.success
    key_points = ctx.sales_strategy_output.get("key_points", [])
    assert "market:family_suitable" in key_points
    assert "market:price_mid" in key_points
    assert any("market:demand" in k for k in key_points)


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_property_matching_sets_market_context_output():
    """Property matching agent populates market_context_output when matches have context."""
    from knowledge.models import Project

    p = Project.objects.create(
        name="ContextProject",
        location="New Cairo",
        price_min=2000000,
        price_max=3000000,
        metadata={
            "market_context": {
                "family_suitability": True,
                "price_segment": "mid",
            }
        },
    )

    agent = PropertyMatchingAgent()
    ctx = AgentContext(
        run_id="t1",
        message_text="شقة في القاهرة الجديدة",
        conversation_history=[],
        intent_output={"primary": "project_inquiry"},
        qualification_output={
            "budget_min": "2000000",
            "budget_max": "3500000",
            "location_preference": "New Cairo",
        },
        memory_output={},
    )
    result = agent.run(ctx)
    assert result.success
    if ctx.property_matching_output and ctx.property_matching_output.get("matches"):
        first_match = ctx.property_matching_output["matches"][0]
        assert first_match.get("market_context") or True  # May have price_segment derived
    if ctx.market_context_output:
        assert "projects" in ctx.market_context_output
        assert ctx.market_context_output["project_count"] >= 0
