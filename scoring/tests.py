"""Scoring engine tests."""
import pytest
from decimal import Decimal
from leads.models import CustomerIdentity, Customer, LeadQualification
from scoring.engine import score_lead, ScoreResult


@pytest.mark.django_db
def test_score_lead_no_qualification():
    identity = CustomerIdentity.objects.create(external_id="t1")
    customer = Customer.objects.create(identity=identity)
    result = score_lead(customer, None)
    assert result.score == 0
    assert result.tier == "cold"


@pytest.mark.django_db
def test_score_lead_with_budget_and_timeline():
    identity = CustomerIdentity.objects.create(external_id="t2")
    customer = Customer.objects.create(identity=identity)
    q = LeadQualification.objects.create(
        customer=customer,
        budget_min=Decimal("2000000"),
        property_type="apartment",
        location_preference="القاهرة الجديدة",
        timeline="خلال شهر",
    )
    result = score_lead(customer, q)
    assert result.score >= 60
    assert result.tier == "hot"
