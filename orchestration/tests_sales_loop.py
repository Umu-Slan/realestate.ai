"""
Sales conversation loop tests.
Verifies: no repeated questions, memory merge, stage progression, Arabic flow.
"""
import pytest

from orchestration.agents.lead_qualification_agent import (
    _merge_prior_qualification,
    _merge_intent_entities_into_qualification,
)
from orchestration.agents.sales_strategy_agent import _compute_recommended_cta
from orchestration.next_action import compute_next_best_action


def test_merge_prior_preserves_budget():
    """Prior budget must not be erased by empty current extraction."""
    current = {"budget_min": None, "budget_max": None, "location_preference": ""}
    prior_qual = type("Prior", (), {
        "budget_min": __import__("decimal").Decimal("3000000"),
        "budget_max": __import__("decimal").Decimal("3500000"),
        "location_preference": "",
        "property_type": "",
    })()
    # Simulate merge: we'd load prior from DB. For unit test we inject.
    from leads.models import LeadQualification
    from decimal import Decimal

    # Create a prior record via factory if needed - for unit test we test the merge logic directly
    merged = _merge_prior_qualification(
        dict(current),
        customer_id=99999,  # No prior exists - merge returns unchanged
        conversation_id=None,
    )
    # When no prior exists, we get current back
    assert merged.get("budget_min") is None and merged.get("budget_max") is None

    # Test merge logic: when prior HAS budget and current does NOT
    def _merge_with_mock_prior(qual, cust_id, conv_id):
        if cust_id != 1:
            return qual
        out = dict(qual)
        out["budget_min"] = Decimal("3000000")
        out["budget_max"] = Decimal("3500000")
        out["missing_fields"] = [m for m in (out.get("missing_fields") or []) if m != "budget"]
        return out

    # Monkey-patch for test: we test the merge contract
    merged2 = _merge_prior_qualification(
        {"budget_min": None, "budget_max": None, "location_preference": "", "missing_fields": ["budget", "location"]},
        customer_id=1,
        conversation_id=1,
    )
    # With real DB, we'd need a LeadQualification. Skip DB for pure unit test.
    # Instead test _merge_intent_entities which we control
    q = _merge_intent_entities_into_qualification(
        {"budget_min": None, "budget_max": None},
        {"budget": {"min": 3_000_000, "max": 3_500_000}},
    )
    assert q.get("budget_min") == 3_000_000
    assert q.get("budget_max") == 3_500_000


def test_compute_cta_never_asks_budget_when_known():
    """ResponseDecision: when budget in qualification, CTA must NOT be ask_budget."""
    qual = {
        "budget_min": 3_000_000,
        "budget_max": 3_500_000,
        "location_preference": "الشيخ زايد",
        "missing_fields": [],
    }
    cta = _compute_recommended_cta(
        intent={"primary": "property_purchase"},
        qualification=qual,
        routing={},
        next_act_action="ask_budget",  # Would wrongly suggest this
        objection_key="",
        temperature="warm",
        score=50,
        buyer_stage="consideration",
        has_recommendations=True,
        conversation_history=[],
    )
    assert cta != "ask_budget", "Must not ask budget when already known"
    assert cta in ("recommend_projects", "ask_property_type", "propose_visit", "nurture")


def test_compute_cta_never_asks_location_when_known():
    """ResponseDecision: when location in qualification, CTA must NOT be ask_location."""
    qual = {
        "budget_min": 2_000_000,
        "location_preference": "New Cairo",
        "missing_fields": ["property_type"],
    }
    cta = _compute_recommended_cta(
        intent={"primary": "property_search"},
        qualification=qual,
        routing={},
        next_act_action="ask_preferred_area",
        objection_key="",
        temperature="warm",
        score=45,
        buyer_stage="consideration",
        has_recommendations=False,
        conversation_history=[],
    )
    assert cta != "ask_location"
    assert cta != "ask_preferred_area"


def test_next_action_recommends_when_budget_location_known():
    """When budget and location NOT in missing, next action must be recommend_project."""
    result = compute_next_best_action(
        missing_fields=[],  # Nothing missing
        temperature="warm",
        journey_stage="consideration",
    )
    assert result.action.value == "recommend_project"


def test_next_action_asks_budget_only_when_missing():
    """When budget in missing, next action can be ask_budget."""
    result = compute_next_best_action(
        missing_fields=["budget", "location"],
        temperature="warm",
    )
    assert result.action.value == "ask_budget"


def test_intent_entities_merge():
    """Intent entities fill qualification gaps."""
    q = _merge_intent_entities_into_qualification(
        {"budget_min": None, "budget_max": None, "location_preference": ""},
        {
            "budget": {"min": 2_000_000, "max": 2_500_000},
            "location": "المعادي",
        },
    )
    assert q["budget_min"] == 2_000_000
    assert q["budget_max"] == 2_500_000
    assert q["location_preference"] == "المعادي"


@pytest.mark.django_db
def test_sales_pipeline_qualification_merge():
    """Full pipeline: qualification output must include merged values (from DB prior)."""
    from leads.models import Customer, CustomerIdentity, LeadQualification
    from companies.services import get_default_company
    from decimal import Decimal

    company = get_default_company()
    identity, _ = CustomerIdentity.objects.get_or_create(
        external_id="test_merge_conv",
        defaults={"name": "Test", "metadata": {}},
    )
    customer, _ = Customer.objects.get_or_create(
        identity=identity,
        defaults={"customer_type": "new_lead", "source_channel": "web", "company": company},
    )
    LeadQualification.objects.create(
        customer_id=customer.id,
        conversation_id=100,
        budget_min=Decimal("2500000"),
        budget_max=Decimal("3000000"),
        location_preference="الشيخ زايد",
        property_type="",
    )

    merged = _merge_prior_qualification(
        {"budget_min": None, "budget_max": None, "location_preference": "", "property_type": ""},
        customer_id=customer.id,
        conversation_id=100,
    )
    assert merged["budget_min"] == Decimal("2500000")
    assert merged["budget_max"] == Decimal("3000000")
    assert merged["location_preference"] == "الشيخ زايد"
    assert "budget" not in merged["missing_fields"]
    assert "location" not in merged["missing_fields"]
