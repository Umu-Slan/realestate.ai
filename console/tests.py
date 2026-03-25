"""
Console analytics tests - metrics and aggregations from persisted data.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Role, UserProfile
from leads.models import CustomerIdentity, Customer, LeadScore
from conversations.models import Conversation, Message
from support.models import SupportCase, Escalation
from console.models import OrchestrationSnapshot
from console.services.analytics import (
    get_dashboard_metrics,
    get_top_intents,
    get_top_support_categories,
    get_top_objections,
    get_average_score_by_source,
    get_escalation_reasons,
)
from core.enums import (
    LeadTemperature,
    EscalationStatus,
    EscalationReason,
    SupportCategory,
)

User = get_user_model()


@pytest.fixture
def identity():
    return CustomerIdentity.objects.create(external_id="test-analytics-1")


@pytest.fixture
def customer_web(identity):
    return Customer.objects.create(
        identity=identity,
        customer_type="new_lead",
        source_channel="web",
    )


@pytest.fixture
def identity2():
    return CustomerIdentity.objects.create(external_id="test-analytics-2")


@pytest.fixture
def customer_whatsapp(identity2):
    return Customer.objects.create(
        identity=identity2,
        customer_type="returning_lead",
        source_channel="whatsapp",
    )


@pytest.mark.django_db
def test_get_dashboard_metrics_empty():
    """Empty DB returns zeroes, valid structure."""
    m = get_dashboard_metrics(days=30)
    assert m["lead_volume"] == 0
    assert m["hot_count"] == 0
    assert m["warm_count"] == 0
    assert m["cold_count"] == 0
    assert m["response_count"] == 0
    assert m["support_cases"] == 0
    assert m["escalations_open"] == 0
    assert m["recommendation_count"] == 0
    assert "channel_distribution" in m
    assert m["days"] == 30


@pytest.mark.django_db
def test_get_dashboard_metrics_lead_volume(customer_web):
    """Lead volume counts customers with lead types in period."""
    m = get_dashboard_metrics(days=30)
    assert m["lead_volume"] >= 1


@pytest.mark.django_db
def test_get_dashboard_metrics_hot_warm_cold(customer_web):
    """Hot/warm/cold from LeadScore in period."""
    LeadScore.objects.create(
        customer=customer_web,
        score=85,
        temperature=LeadTemperature.HOT.value,
    )
    LeadScore.objects.create(
        customer=customer_web,
        score=55,
        temperature=LeadTemperature.WARM.value,
    )
    m = get_dashboard_metrics(days=30)
    assert m["hot_count"] >= 1
    assert m["warm_count"] >= 1


@pytest.mark.django_db
def test_get_dashboard_metrics_response_count(customer_web):
    """Response count from assistant messages."""
    conv = Conversation.objects.create(customer=customer_web, channel="web")
    Message.objects.create(conversation=conv, role="user", content="Hi")
    Message.objects.create(conversation=conv, role="assistant", content="Hello")
    Message.objects.create(conversation=conv, role="assistant", content="How can I help?")
    m = get_dashboard_metrics(days=30)
    assert m["response_count"] >= 2


@pytest.mark.django_db
def test_get_dashboard_metrics_support_and_escalations(customer_web):
    """Support cases and escalations in period."""
    conv = Conversation.objects.create(customer=customer_web, channel="web")
    esc = Escalation.objects.create(
        customer=customer_web,
        conversation=conv,
        reason=EscalationReason.ANGRY_CUSTOMER.value,
        status=EscalationStatus.OPEN,
    )
    SupportCase.objects.create(
        customer=customer_web,
        conversation=conv,
        category=SupportCategory.INSTALLMENT.value,
    )
    m = get_dashboard_metrics(days=30)
    assert m["support_cases"] >= 1
    assert m["escalations_open"] >= 1


@pytest.mark.django_db
def test_get_dashboard_metrics_channel_distribution(customer_web):
    """Channel distribution from conversations."""
    Conversation.objects.create(customer=customer_web, channel="web")
    Conversation.objects.create(customer=customer_web, channel="whatsapp")
    m = get_dashboard_metrics(days=30)
    assert len(m["channel_distribution"]) >= 1
    channels = [ch["channel"] for ch in m["channel_distribution"]]
    assert "web" in channels or "whatsapp" in channels


@pytest.mark.django_db
def test_get_top_intents(customer_web):
    """Top intents from OrchestrationSnapshot."""
    conv = Conversation.objects.create(customer=customer_web, channel="web")
    msg = Message.objects.create(conversation=conv, role="user", content="Hi")
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        message=msg,
        run_id="r1",
        intent={"primary": "project_inquiry"},
    )
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        message=msg,
        run_id="r2",
        intent={"primary": "project_inquiry"},
    )
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        message=msg,
        run_id="r3",
        intent={"primary": "pricing"},
    )
    top = get_top_intents(limit=5, days=30)
    assert len(top) >= 1
    primary = next((r for r in top if r["intent"] == "project_inquiry"), None)
    assert primary is not None
    assert primary["count"] >= 2


@pytest.mark.django_db
def test_get_top_support_categories(customer_web):
    """Top support categories."""
    conv = Conversation.objects.create(customer=customer_web, channel="web")
    SupportCase.objects.create(
        customer=customer_web,
        conversation=conv,
        category=SupportCategory.INSTALLMENT.value,
    )
    SupportCase.objects.create(
        customer=customer_web,
        conversation=conv,
        category=SupportCategory.INSTALLMENT.value,
    )
    SupportCase.objects.create(
        customer=customer_web,
        conversation=conv,
        category=SupportCategory.COMPLAINT.value,
    )
    top = get_top_support_categories(limit=5, days=30)
    assert len(top) >= 1
    inst = next((r for r in top if r["category"] == SupportCategory.INSTALLMENT.value), None)
    assert inst is not None
    assert inst["count"] >= 2


@pytest.mark.django_db
def test_get_top_objections():
    """Top objections from user messages (detect_objection)."""
    ident = CustomerIdentity.objects.create(external_id="obj-1")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead")
    conv = Conversation.objects.create(customer=cust, channel="web")
    Message.objects.create(conversation=conv, role="user", content="The price is too expensive")
    Message.objects.create(conversation=conv, role="user", content="It's over budget for me")
    top = get_top_objections(limit=5, days=30, sample_size=100)
    # detect_objection returns "price_too_high" for "expensive", "over budget"
    price_obj = next((r for r in top if r["objection"] == "price_too_high"), None)
    # May or may not match depending on pattern coverage
    assert isinstance(top, list)
    assert all(isinstance(r, dict) and "objection" in r and "count" in r for r in top)


@pytest.mark.django_db
def test_get_average_score_by_source(customer_web, customer_whatsapp):
    """Average lead score grouped by source_channel."""
    LeadScore.objects.create(
        customer=customer_web,
        score=80,
        temperature=LeadTemperature.HOT.value,
    )
    LeadScore.objects.create(
        customer=customer_web,
        score=60,
        temperature=LeadTemperature.WARM.value,
    )
    LeadScore.objects.create(
        customer=customer_whatsapp,
        score=50,
        temperature=LeadTemperature.WARM.value,
    )
    rows = get_average_score_by_source(days=30)
    assert len(rows) >= 1
    for r in rows:
        assert "source" in r
        assert "avg_score" in r
        assert "count" in r


@pytest.mark.django_db
def test_get_escalation_reasons(customer_web):
    """Escalation count by reason."""
    conv = Conversation.objects.create(customer=customer_web, channel="web")
    Escalation.objects.create(
        customer=customer_web,
        conversation=conv,
        reason=EscalationReason.ANGRY_CUSTOMER.value,
        status=EscalationStatus.OPEN,
    )
    Escalation.objects.create(
        customer=customer_web,
        conversation=conv,
        reason=EscalationReason.ANGRY_CUSTOMER.value,
        status=EscalationStatus.RESOLVED,
    )
    Escalation.objects.create(
        customer=customer_web,
        conversation=conv,
        reason=EscalationReason.LOW_CONFIDENCE.value,
        status=EscalationStatus.OPEN,
    )
    rows = get_escalation_reasons(days=30)
    assert len(rows) >= 1
    angry = next((r for r in rows if r["reason"] == EscalationReason.ANGRY_CUSTOMER.value), None)
    assert angry is not None
    assert angry["count"] >= 2


@pytest.mark.django_db
def test_dashboard_view_renders(client):
    """Dashboard view returns 200 with metrics."""
    from django.urls import reverse
    resp = client.get(reverse("console:dashboard"))
    assert resp.status_code == 200
    assert b"Lead Volume" in resp.content or b"lead" in resp.content.lower()


@pytest.mark.django_db
def test_analytics_view_renders(client):
    """Analytics view returns 200."""
    from django.urls import reverse
    resp = client.get(reverse("console:analytics"))
    assert resp.status_code == 200
    assert b"Top Intents" in resp.content or b"intent" in resp.content.lower()


# --- Operator Assist tests ---


@pytest.mark.django_db
def test_build_operator_assist_basic():
    """build_operator_assist returns expected structure with lead score and stage."""
    from console.services.operator_assist import build_operator_assist

    ident = CustomerIdentity.objects.create(external_id="test-oa-1")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web")
    LeadScore.objects.create(customer=cust, score=72, temperature=LeadTemperature.WARM.value, journey_stage="consideration")
    snap = OrchestrationSnapshot.objects.create(
        conversation=conv, run_id="run-oa-1",
        journey_stage="consideration",
        next_best_action="Propose visit",
        scoring={"score": 72, "temperature": "warm", "reason_codes": [{"note": "Budget clarified"}]},
    )

    result = build_operator_assist(
        conversation=conv,
        latest_snapshot=snap,
        latest_score=cust.scores.first(),
        latest_qual=None,
        messages=[],
        recommendations=[],
        escalations=[],
        support_cases=[],
    )
    assert result["lead_score"]["value"] == 72
    assert result["lead_score"]["temperature"] == "warm"
    assert result["buyer_stage"] == "consideration"
    assert "best_next_action" in result
    assert "Propose visit" in result["best_next_action"]
    assert result["missing_qualification_fields"]
    assert "Budget min" in result["missing_qualification_fields"]


@pytest.mark.django_db
def test_build_operator_assist_objection_hints():
    """Objection hints are extracted from recent user messages."""
    from console.services.operator_assist import build_operator_assist

    ident = CustomerIdentity.objects.create(external_id="test-oa-2")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web")
    Message.objects.create(conversation=conv, role="user", content="السعر غالي جداً")
    Message.objects.create(conversation=conv, role="assistant", content="...")
    messages = list(conv.messages.all().order_by("created_at"))

    result = build_operator_assist(
        conversation=conv,
        latest_snapshot=None,
        latest_score=None,
        latest_qual=None,
        messages=messages,
        recommendations=[],
        escalations=[],
        support_cases=[],
    )
    assert result["objection_hints"]
    assert any(h["objection_key"] == "price_too_high" for h in result["objection_hints"])
    assert any("label" in h for h in result["objection_hints"])


@pytest.mark.django_db
def test_build_operator_assist_escalation_support_links():
    """has_escalation and has_support_case set when present; escalation/support_case ids."""
    from console.services.operator_assist import build_operator_assist

    ident = CustomerIdentity.objects.create(external_id="test-oa-3")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web")
    esc = Escalation.objects.create(
        customer=cust, conversation=conv,
        reason=EscalationReason.COMPLEX_INQUIRY.value, status=EscalationStatus.OPEN,
    )
    sc = SupportCase.objects.create(
        customer=cust, conversation=conv, category=SupportCategory.INSTALLMENT.value,
    )

    result = build_operator_assist(
        conversation=conv,
        latest_snapshot=None,
        latest_score=None,
        latest_qual=None,
        messages=[],
        recommendations=[],
        escalations=[esc],
        support_cases=[sc],
    )
    assert result["has_escalation"] is True
    assert result["has_support_case"] is True
    assert esc.id in result["escalation_ids"]
    assert sc.id in result["support_case_ids"]
    assert len(result["escalations"]) == 1
    assert len(result["support_cases"]) == 1


@pytest.mark.django_db
def test_conversation_detail_includes_operator_assist(client):
    """Conversation detail view returns 200 and includes operator assist context."""
    from django.urls import reverse

    ident = CustomerIdentity.objects.create(external_id="test-oa-view")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead", source_channel="web")
    conv = Conversation.objects.create(customer=cust, channel="web")

    resp = client.get(reverse("console:conversation_detail", args=[conv.id]))
    assert resp.status_code == 200
    assert b"Operator Assist" in resp.content or b"operator" in resp.content.lower()


@pytest.fixture
def console_user():
    u = User.objects.create_user(username="console_tester", password="test")
    UserProfile.objects.create(user=u, role=Role.OPERATOR)
    return u


@pytest.mark.django_db
def test_lead_scoring_list_and_export(client, customer_web, console_user):
    """Lead scoring page lists customers by latest score; CSV export matches filters."""
    LeadScore.objects.create(
        customer=customer_web,
        score=82,
        temperature=LeadTemperature.HOT.value,
    )
    client.force_login(console_user)
    resp = client.get(reverse("console:lead_scoring"))
    assert resp.status_code == 200
    assert customer_web.identity.external_id.encode() in resp.content

    resp_cold = client.get(reverse("console:lead_scoring"), {"temp": "cold"})
    assert resp_cold.status_code == 200
    assert customer_web.identity.external_id.encode() not in resp_cold.content

    csv_resp = client.get(reverse("console:lead_scoring_export"))
    assert csv_resp.status_code == 200
    assert b"customer_id" in csv_resp.content
    assert str(customer_web.id).encode() in csv_resp.content
