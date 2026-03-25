"""Lead intelligence and attribution analytics tests (database)."""
import pytest

from channels.attribution import apply_attribution_to_models
from console.models import OrchestrationSnapshot
from console.services.lead_intelligence import build_lead_intelligence_report
from conversations.models import Conversation, Message
from core.enums import LeadTemperature
from knowledge.models import Project
from leads.models import Customer, CustomerIdentity, LeadScore
from recommendations.models import Recommendation


@pytest.mark.django_db
def test_apply_attribution_merges_metadata():
    ident = CustomerIdentity.objects.create(external_id="attr-merge-1")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web", metadata={})
    apply_attribution_to_models(cust, conv, {"utm_source": "meta", "utm_campaign": "c1"})
    conv.refresh_from_db()
    cust.refresh_from_db()
    assert conv.metadata.get("attribution", {}).get("utm_campaign") == "c1"
    assert cust.metadata.get("attribution_first", {}).get("utm_campaign") == "c1"


@pytest.mark.django_db
def test_lead_intelligence_report_structure():
    ident = CustomerIdentity.objects.create(external_id="intel-test-1")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    Conversation.objects.create(customer=cust, channel="web", metadata={"attribution": {"utm_campaign": "unit_test"}})
    LeadScore.objects.create(customer=cust, score=70, temperature=LeadTemperature.WARM.value)
    report = build_lead_intelligence_report(days=30)
    assert "campaign_rows" in report
    assert "geo_rows" in report
    assert "objections" in report
    assert "insights" in report
    assert report["days"] == 30


@pytest.mark.django_db
def test_objections_merge_from_snapshot():
    ident = CustomerIdentity.objects.create(external_id="intel-test-2")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web")
    msg = Message.objects.create(conversation=conv, role="user", content="test")
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        message=msg,
        run_id="r-intel-1",
        routing={"objection_key": "price_too_high"},
    )
    report = build_lead_intelligence_report(days=30)
    keys = {o["objection"] for o in report["objections"]}
    assert "price_too_high" in keys or len(report["objections"]) >= 1


@pytest.mark.django_db
def test_project_intel_requires_recommendation():
    from companies.models import Company

    company = Company.objects.create(name="Co Intel", slug="intel-co-test")
    ident = CustomerIdentity.objects.create(external_id="intel-test-3")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web", company=company)
    proj = Project.objects.create(name="Palm Hills", company=company, location="Cairo")
    Recommendation.objects.create(customer=cust, project=proj, rationale="fit")
    LeadScore.objects.create(customer=cust, score=88, temperature=LeadTemperature.HOT.value)
    report = build_lead_intelligence_report(days=30)
    names = [p["name"] for p in report["projects"]]
    assert "Palm Hills" in names
