"""
Tests for market/context intelligence layer.
Ensures honesty: only supported facts, no hallucination.
"""
import pytest

try:
    import pgvector  # noqa: F401
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

from knowledge.services.market_context import (
    ProjectMarketContext,
    get_project_market_context,
    get_projects_market_context,
)


def test_project_market_context_to_safe_dict_only_populated():
    """to_safe_dict returns only fields with values."""
    ctx = ProjectMarketContext(
        project_id=1,
        area_attractiveness="high",
        family_suitability=True,
        investment_suitability=None,
    )
    d = ctx.to_safe_dict()
    assert d["project_id"] == 1
    assert d["area_attractiveness"] == "high"
    assert d["family_suitability"] is True
    assert "investment_suitability" not in d
    assert "price_segment" not in d


def test_project_market_context_has_any():
    """has_any True only when at least one fact populated."""
    assert ProjectMarketContext(project_id=1).has_any is False
    assert ProjectMarketContext(project_id=1, area_attractiveness="high").has_any is True
    assert ProjectMarketContext(project_id=1, family_suitability=True).has_any is True
    assert ProjectMarketContext(project_id=1, demand_cues=["high_demand"]).has_any is True


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_get_project_market_context_returns_none_for_missing_project():
    """Missing project returns None."""
    assert get_project_market_context(99999) is None


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_get_project_market_context_from_metadata():
    """Load market context from Project.metadata."""
    from knowledge.models import Project

    p = Project.objects.create(
        name="TestProject",
        location="New Cairo",
        price_min=2000000,
        price_max=3000000,
        metadata={
            "market_context": {
                "area_attractiveness": "high",
                "family_suitability": True,
                "investment_suitability": True,
                "price_segment": "mid",
                "financing_style": "installments",
                "demand_cues": ["high_demand", "new_release"],
                "source": "manual",
            }
        },
    )
    ctx = get_project_market_context(p.id)
    assert ctx is not None
    assert ctx.area_attractiveness == "high"
    assert ctx.family_suitability is True
    assert ctx.investment_suitability is True
    assert ctx.price_segment == "mid"
    assert ctx.financing_style == "installments"
    assert "high_demand" in (ctx.demand_cues or [])
    d = ctx.to_safe_dict()
    assert d["area_attractiveness"] == "high"


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_get_project_market_context_derives_price_segment():
    """Price segment derived from project pricing when not in metadata."""
    from knowledge.models import Project

    p = Project.objects.create(
        name="BudgetProject",
        location="6 October",
        price_min=800000,
        price_max=1200000,
    )
    ctx = get_project_market_context(p.id)
    assert ctx is not None
    assert ctx.price_segment == "entry"


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_get_project_market_context_no_hallucination():
    """Empty metadata returns None - no fabricated facts."""
    from knowledge.models import Project

    p = Project.objects.create(
        name="BareProject",
        location="Maadi",
    )
    ctx = get_project_market_context(p.id)
    # No price, no metadata -> returns None (no hallucination)
    assert ctx is None


@pytest.mark.django_db
@pytest.mark.skipif(not HAS_PGVECTOR, reason="pgvector required for Django models")
def test_get_projects_market_context_batch():
    """Batch load returns dict of project_id -> context."""
    from knowledge.models import Project

    p1 = Project.objects.create(name="P1", metadata={"market_context": {"area_attractiveness": "high"}})
    p2 = Project.objects.create(name="P2", metadata={"market_context": {"family_suitability": True}})

    result = get_projects_market_context([p1.id, p2.id, 99999])
    assert p1.id in result
    assert p2.id in result
    assert 99999 not in result
    assert result[p1.id].area_attractiveness == "high"
    assert result[p2.id].family_suitability is True
