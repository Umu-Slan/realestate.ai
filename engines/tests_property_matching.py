"""
Tests for production Property Matching Engine.
Covers: budget fit, location fit, property type, bedroom, purpose, financing,
stage, family/lifestyle fit; combined scenarios; ranking.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from engines.property_matching import (
    match_projects,
    _score_budget_fit,
    _score_location_fit,
    _score_property_type_fit,
    _score_bedroom_fit,
    _score_purpose_fit,
    _score_financing_fit,
    _score_stage_fit,
    _score_family_lifestyle_fit,
    _extract_bedroom_from_text,
    FACTOR_WEIGHTS,
    ProjectMatchResult,
    FactorContribution,
)


def _mk_project(**kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", 1)
    p.name = kwargs.get("name", "Project")
    p.name_ar = kwargs.get("name_ar", "")
    p.location = kwargs.get("location", "")
    p.price_min = kwargs.get("price_min")
    p.price_max = kwargs.get("price_max")
    p.property_types = kwargs.get("property_types") or []
    return p


# --- Unit factor tests ---


def test_score_budget_fit_overlap():
    p = _mk_project(price_min=Decimal("2000000"), price_max=Decimal("3000000"))
    fc = _score_budget_fit(p, Decimal("2200000"), Decimal("2800000"), has_verified=True)
    assert fc.score > 0.9
    assert "budget_fit" in fc.reason or "budget" in fc.reason.lower()


def test_score_budget_fit_near():
    p = _mk_project(price_min=Decimal("2500000"), price_max=Decimal("3500000"))
    fc = _score_budget_fit(p, Decimal("2000000"), Decimal("2400000"), has_verified=False)
    assert fc.score > 0.2
    assert fc.tradeoff or "budget" in fc.reason.lower()


def test_score_location_fit_match():
    p = _mk_project(location="New Cairo", name="Towers")
    fc = _score_location_fit(p, "New Cairo", ["new cairo", "القاهرة الجديدة"])
    assert fc.score > 0.9
    assert "location_match" in fc.reason


def test_score_location_fit_mismatch():
    p = _mk_project(location="Maadi", name="Villa")
    fc = _score_location_fit(p, "New Cairo", ["new cairo"])
    assert fc.score < 0.5
    assert fc.tradeoff or "different" in fc.tradeoff.lower()


def test_score_property_type_match():
    p = _mk_project(property_types=["apartment", "villa"])
    fc = _score_property_type_fit(p, "apartment")
    assert fc.score > 0.9
    assert "property_type_match" in fc.reason


def test_score_property_type_mismatch():
    p = _mk_project(property_types=["villa"])
    fc = _score_property_type_fit(p, "apartment")
    assert fc.score < 0.5
    assert fc.tradeoff


def test_extract_bedroom_from_text():
    assert _extract_bedroom_from_text("3BR Apartment") == 3
    assert _extract_bedroom_from_text("شقة 3 غرف") == 3
    assert _extract_bedroom_from_text("2 bedroom") == 2
    assert _extract_bedroom_from_text("villa") is None


def test_score_bedroom_fit_match():
    p = _mk_project(name="3BR Towers")
    fc = _score_bedroom_fit(p, 3, [])
    assert fc.score > 0.8
    assert "bedroom_match" in fc.reason


def test_score_bedroom_fit_unspecified():
    p = _mk_project()
    fc = _score_bedroom_fit(p, None, [])
    assert fc.score == 0.5
    assert "bedroom_unspecified" in fc.reason


def test_score_purpose_fit_investment():
    p = _mk_project()
    mc = {"investment_suitability": True}
    fc = _score_purpose_fit(p, "investment", mc)
    assert fc.score > 0.9
    assert "investment" in fc.reason.lower()


def test_score_purpose_fit_residence():
    p = _mk_project()
    mc = {"family_suitability": True}
    fc = _score_purpose_fit(p, "residence", mc)
    assert fc.score > 0.9


def test_score_financing_fit_installment():
    pp = {"installment_years_min": 5, "installment_years_max": 10}
    fc = _score_financing_fit(pp, "installment", "قسط")
    assert fc.score > 0.9
    assert "installment" in fc.reason.lower()


def test_score_financing_fit_unspecified():
    fc = _score_financing_fit(None, "", "")
    assert fc.score == 0.5


def test_score_stage_fit_ready():
    fc = _score_stage_fit("immediate", "urgent", "shortlisting")
    assert fc.score > 0.8
    assert "ready" in fc.reason.lower() or "delivery" in fc.reason.lower()


def test_score_family_lifestyle_fit():
    mc = {"family_suitability": True}
    fc = _score_family_lifestyle_fit("residence", mc)
    assert fc.score > 0.9


# --- Integration tests ---


def test_match_projects_returns_sorted_by_score():
    projects = [
        _mk_project(id=1, name="A", location="New Cairo", price_min=Decimal("2000000"), price_max=Decimal("3000000")),
        _mk_project(id=2, name="B", location="Maadi", price_min=Decimal("1000000"), price_max=Decimal("2000000")),
    ]
    results = match_projects(
        projects=projects,
        budget_min=Decimal("2500000"),
        budget_max=Decimal("2800000"),
        location_preference="New Cairo",
        loc_search_terms=["new cairo", "القاهرة الجديدة"],
        get_structured_facts=lambda _: None,
        get_market_context=lambda _: None,
    )
    assert len(results) == 2
    assert all(isinstance(r, ProjectMatchResult) for r in results)
    scores = [r.match_score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 1 for s in scores)


def test_match_projects_includes_top_reasons_and_tradeoffs():
    projects = [
        _mk_project(id=1, name="Test", location="New Cairo", price_min=Decimal("2500000"), price_max=Decimal("3500000")),
    ]
    results = match_projects(
        projects=projects,
        budget_min=Decimal("2000000"),
        budget_max=Decimal("2400000"),
        location_preference="New Cairo",
        loc_search_terms=["new cairo"],
        get_structured_facts=lambda _: None,
        get_market_context=lambda _: None,
    )
    assert len(results) == 1
    r = results[0]
    assert isinstance(r.top_reasons, list)
    assert isinstance(r.tradeoffs, list)
    assert r.rationale


def test_weights_inspectable():
    assert "budget_fit" in FACTOR_WEIGHTS
    assert "location_fit" in FACTOR_WEIGHTS
    assert 0 < FACTOR_WEIGHTS["budget_fit"] <= 1
    assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 0.2
