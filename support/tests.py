"""
Support triage, escalation policy, and case creation tests.
"""
import pytest

from support.triage import triage_support
from core.enums import SupportCategory, SupportSeverity, SupportSLABucket, EscalationReason


def test_escalation_reason_angry_customer():
    """Angry customer -> ANGRY_CUSTOMER."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(is_angry=True)
    assert r == EscalationReason.ANGRY_CUSTOMER


def test_escalation_reason_legal_contract():
    """Contract intent -> LEGAL_CONTRACT."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(intent_primary="contract_issue", routing_route="legal_handoff")
    assert r == EscalationReason.LEGAL_CONTRACT


def test_escalation_reason_pricing_exception():
    """Price inquiry without verified pricing -> PRICING_EXCEPTION."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(
        intent_primary="price_inquiry",
        intent_is_price_inquiry=True,
        has_verified_pricing=False,
    )
    assert r == EscalationReason.PRICING_EXCEPTION


def test_escalation_reason_unavailable_critical_info():
    """Safe response policy -> UNAVAILABLE_CRITICAL_INFO."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(routing_safe_response_policy=True)
    assert r == EscalationReason.UNAVAILABLE_CRITICAL_INFO


def test_escalation_reason_low_confidence():
    """Requires human review -> LOW_CONFIDENCE."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(routing_requires_human_review=True)
    assert r == EscalationReason.LOW_CONFIDENCE


def test_escalation_reason_severe_complaint():
    """Complaint intent (no angry) -> SEVERE_COMPLAINT."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(intent_primary="support_complaint")
    assert r == EscalationReason.SEVERE_COMPLAINT


def test_escalation_reason_policy_forced():
    """Policy forced escalation -> NEGOTIATION_BEYOND_POLICY or specific."""
    from orchestration.escalation_policy import resolve_escalation_reason
    r = resolve_escalation_reason(policy_forced_escalation=True, escalation_flags=["policy_forced_escalation"])
    assert r in (EscalationReason.NEGOTIATION_BEYOND_POLICY, EscalationReason.LEGAL_CONTRACT, EscalationReason.PRICING_EXCEPTION)


def test_handoff_summary_structure():
    """Handoff summary contains required fields."""
    from orchestration.handoff import build_handoff_summary
    h = build_handoff_summary(
        customer_type="existing_customer",
        intent={"primary": "installment_inquiry"},
        qualification={"budget_min": 2e6, "location_preference": "New Cairo"},
        scoring={"score": 65, "temperature": "warm"},
        routing={"route": "support", "queue": "installment_queue"},
        next_action={"action": "escalate", "reason": "Complex installment query"},
        risk_notes=["Escalation ready"],
    )
    assert "customer_type" in h
    assert "intent_summary" in h
    assert "qualification_summary" in h
    assert "score_and_category" in h
    assert "support_category" in h
    assert "routing" in h
    assert "risk_notes" in h
    assert "recommended_next_step" in h


def test_triage_normal_support_request():
    """Normal support request -> medium severity, general queue."""
    triage = triage_support(
        intent_primary="installment_inquiry",
        support_category="installment",
        is_angry=False,
        routing_route="support",
        routing_escalation_ready=False,
    )
    assert triage.category == SupportCategory.INSTALLMENT.value
    assert triage.severity == SupportSeverity.MEDIUM.value
    assert triage.sla_bucket in (SupportSLABucket.P2.value, SupportSLABucket.P3.value)
    assert triage.assigned_queue == "installment_queue"
    assert triage.escalation_trigger == ""


def test_triage_angry_complaint():
    """Angry complaint -> high severity, P1/P2 SLA, escalation trigger."""
    triage = triage_support(
        intent_primary="support_complaint",
        support_category="complaint",
        is_angry=True,
        routing_route="support_escalation",
        routing_escalation_ready=True,
    )
    assert triage.category == SupportCategory.COMPLAINT.value
    assert triage.severity in (SupportSeverity.HIGH.value, SupportSeverity.CRITICAL.value)
    assert triage.sla_bucket == SupportSLABucket.P1.value
    assert triage.assigned_queue == "urgent_support"
    assert triage.escalation_trigger == "angry_customer"


def test_triage_documentation_request():
    """Documentation request -> documentation queue."""
    triage = triage_support(
        intent_primary="documentation_inquiry",
        support_category="documentation",
        is_angry=False,
        routing_route="support",
        routing_escalation_ready=False,
    )
    assert triage.category == SupportCategory.DOCUMENTATION.value
    assert triage.severity == SupportSeverity.MEDIUM.value
    assert triage.assigned_queue == "documentation_queue"


def test_triage_handover_question():
    """Handover/delivery question -> handover category."""
    triage = triage_support(
        intent_primary="delivery_inquiry",
        support_category="handover",
        is_angry=False,
        routing_route="support",
        routing_escalation_ready=False,
    )
    assert triage.category == SupportCategory.HANDOVER.value
    assert triage.assigned_queue in ("general_support", "priority_support")


@pytest.mark.django_db
def test_support_case_created_on_support_message():
    """Support-related message creates SupportCase via support chat API."""
    from django.test import Client
    from conversations.models import Conversation
    from support.models import SupportCase

    client = Client()
    resp = client.post(
        "/api/engines/support/",
        {"message": "متى القسط القادم؟ أريد معرفة جدول التقسيط", "use_llm": False},
        content_type="application/json",
    )
    assert resp.status_code == 200

    conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").first()
    assert conv is not None
    cases = SupportCase.objects.filter(conversation=conv)
    assert cases.exists(), "SupportCase should be created for installment inquiry"
    case = cases.first()
    assert case.category in (SupportCategory.INSTALLMENT.value, SupportCategory.GENERAL_SUPPORT.value, "installment", "general_support")
    assert case.customer is not None
    assert case.conversation == conv
    assert case.assigned_queue
    assert case.severity
    assert case.sla_bucket


@pytest.mark.django_db
def test_angry_complaint_creates_escalation():
    """Angry complaint creates SupportCase with escalation and handoff summary."""
    from django.test import Client
    from conversations.models import Conversation
    from support.models import SupportCase, Escalation

    client = Client()
    resp = client.post(
        "/api/engines/support/",
        {"message": "أنا غاضب جداً! العقد متأخر والقسط غلط. أريد التحدث مع المدير الآن.", "is_angry": True, "use_llm": False},
        content_type="application/json",
    )
    assert resp.status_code == 200

    conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").first()
    assert conv is not None
    cases = SupportCase.objects.filter(conversation=conv)
    assert cases.exists()
    case = cases.first()
    assert case.severity in (SupportSeverity.HIGH.value, SupportSeverity.CRITICAL.value, SupportSeverity.MEDIUM.value, "high", "critical", "medium")
    esc = Escalation.objects.filter(customer=conv.customer).first()
    assert esc is not None
    assert esc.reason == EscalationReason.ANGRY_CUSTOMER.value
    assert esc.handoff_summary
    assert "customer_identity" in esc.handoff_summary
    assert "recommended_next_step" in esc.handoff_summary or "intent" in esc.handoff_summary
