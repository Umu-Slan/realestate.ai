"""Tests for improvement aggregation logic."""
import pytest
from decimal import Decimal
from django.utils import timezone

from improvement.models import ImprovementSignal
from improvement.services.aggregation import (
    aggregate_improvement_signals,
    _upsert_signal,
    _aggregate_escalation_reasons,
    _aggregate_support_categories,
)
from improvement.services.recommendations import generate_operator_recommendations
from leads.models import CustomerIdentity, Customer, LeadQualification
from support.models import Escalation
from conversations.models import Conversation
from core.enums import EscalationReason, EscalationStatus, SourceChannel


@pytest.mark.django_db
def test_upsert_signal_creates_new():
    """_upsert_signal creates new signal when none exists."""
    before = ImprovementSignal.objects.count()
    _upsert_signal(
        issue_type="escalation_reason",
        source_feature="support",
        pattern_key="angry_customer",
        frequency=3,
        affected_mode="",
        affected_intent="",
        example_refs=[{"type": "escalation", "id": 1}],
        recommended_action="Add FAQ",
    )
    assert ImprovementSignal.objects.count() == before + 1
    s = ImprovementSignal.objects.get(pattern_key="angry_customer")
    assert s.frequency == 3
    assert s.issue_type == "escalation_reason"


@pytest.mark.django_db
def test_upsert_signal_updates_existing():
    """_upsert_signal updates frequency when pattern exists."""
    ImprovementSignal.objects.create(
        issue_type="escalation_reason",
        source_feature="support",
        pattern_key="angry_customer",
        frequency=2,
        recommended_action="Add FAQ",
    )
    _upsert_signal(
        issue_type="escalation_reason",
        source_feature="support",
        pattern_key="angry_customer",
        frequency=1,
        affected_mode="",
        affected_intent="",
        example_refs=[],
        recommended_action="",
    )
    s = ImprovementSignal.objects.get(pattern_key="angry_customer")
    assert s.frequency == 3


@pytest.mark.django_db
def test_aggregate_escalation_reasons():
    """Aggregation from Escalation populates signals."""
    ident = CustomerIdentity.objects.create(external_id="test-esc-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)
    Escalation.objects.create(
        customer=cust,
        conversation=conv,
        reason=EscalationReason.ANGRY_CUSTOMER,
        status=EscalationStatus.OPEN,
    )
    Escalation.objects.create(
        customer=cust,
        conversation=conv,
        reason=EscalationReason.ANGRY_CUSTOMER,
        status=EscalationStatus.OPEN,
    )
    Escalation.objects.create(
        customer=cust,
        conversation=conv,
        reason=EscalationReason.LOW_CONFIDENCE,
        status=EscalationStatus.OPEN,
    )
    count = _aggregate_escalation_reasons(days=7, company_id=None)
    assert count >= 2
    signals = list(ImprovementSignal.objects.filter(issue_type="escalation_reason"))
    assert len(signals) >= 1
    angry = next((s for s in signals if s.pattern_key == EscalationReason.ANGRY_CUSTOMER), None)
    assert angry is not None
    assert angry.frequency >= 2


@pytest.mark.django_db
def test_aggregate_support_categories():
    """Aggregation from SupportCase populates signals."""
    from support.models import SupportCase
    from core.enums import SupportCategory, SupportStatus
    ident = CustomerIdentity.objects.create(external_id="test-supp-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)
    SupportCase.objects.create(
        customer=cust,
        conversation=conv,
        category=SupportCategory.INSTALLMENT,
        status=SupportStatus.OPEN,
    )
    SupportCase.objects.create(
        customer=cust,
        conversation=conv,
        category=SupportCategory.INSTALLMENT,
        status=SupportStatus.OPEN,
    )
    count = _aggregate_support_categories(days=7, company_id=None)
    assert count >= 1
    signals = list(ImprovementSignal.objects.filter(issue_type="support_category"))
    assert len(signals) >= 1


@pytest.mark.django_db
def test_aggregate_improvement_signals_returns_counts():
    """aggregate_improvement_signals returns dict of counts."""
    result = aggregate_improvement_signals(days=7, company_id=None)
    assert isinstance(result, dict)
    assert "corrected_responses" in result
    assert "escalation_reasons" in result
    assert "support_categories" in result
    assert "objection_types" in result
    assert "low_confidence" in result
    assert "missing_qualification" in result
    assert "score_routing_disagreement" in result
    assert "failed_recommendation" in result
    assert "reinforcement_signals" in result


@pytest.mark.django_db
def test_record_reinforcement_signal():
    """record_reinforcement_signal creates structured records with links."""
    from improvement.models import ReinforcementSignal
    from improvement.services.reinforcement_signals import (
        record_reinforcement_signal,
        get_reinforcement_signals_for_insights,
    )

    ident = CustomerIdentity.objects.create(external_id="test-reinforce-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    sig = record_reinforcement_signal(
        "user_continued_conversation",
        conversation_id=conv.id,
        customer_id=cust.id,
        journey_stage="consideration",
        strategy="nurture",
        intent_primary="project_inquiry",
    )
    assert sig is not None
    assert sig.signal_type == "user_continued_conversation"
    assert sig.conversation_id == conv.id
    assert sig.customer_id == cust.id
    assert sig.journey_stage == "consideration"
    assert sig.strategy == "nurture"


@pytest.mark.django_db
def test_record_reinforcement_signal_invalid_type():
    """Invalid signal type returns None."""
    from improvement.services.reinforcement_signals import record_reinforcement_signal

    sig = record_reinforcement_signal("invalid_type", conversation_id=1)
    assert sig is None


@pytest.mark.django_db
def test_reinforcement_signals_aggregate_to_improvement():
    """ReinforcementSignal aggregates into ImprovementSignal on refresh."""
    from improvement.models import ReinforcementSignal
    from improvement.services.reinforcement_signals import record_reinforcement_signal

    ident = CustomerIdentity.objects.create(external_id="test-reinforce-agg")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    record_reinforcement_signal(
        "user_disengaged",
        conversation_id=conv.id,
        customer_id=cust.id,
        journey_stage="awareness",
        strategy="nurture",
    )
    record_reinforcement_signal(
        "objection_unresolved",
        conversation_id=conv.id,
        customer_id=cust.id,
        metadata={"objection_key": "price_too_high"},
    )

    result = aggregate_improvement_signals(days=7, company_id=None)
    assert result.get("reinforcement_signals", 0) >= 2
    improvement_recs = list(
        ImprovementSignal.objects.filter(issue_type="reinforcement_outcome")
    )
    assert len(improvement_recs) >= 1


@pytest.mark.django_db
def test_aggregate_corrected_responses_with_sales_linkage():
    """Corrections with sales linkage create strategy/objection/stage patterns in ImprovementSignal."""
    from leads.models import CustomerIdentity, Customer
    from audit.models import HumanCorrection
    from conversations.models import Conversation, Message

    ident = CustomerIdentity.objects.create(external_id="test-correction-link")
    cust = Customer.objects.create(identity=ident, customer_type="new_lead")
    conv = Conversation.objects.create(customer=cust, channel="web")
    msg = Message.objects.create(conversation=conv, role="assistant", content="Original")

    HumanCorrection.objects.create(
        subject_type="message",
        subject_id=str(msg.id),
        field_name="response",
        original_value="Original",
        corrected_value="Fixed",
        corrected_by="tester",
        message=msg,
        conversation=conv,
        customer=cust,
        mode="sales",
        issue_type="objection_handling",
        sales_linkage={
            "strategy": "nurture",
            "objection_type": "price_too_high",
            "recommendation_quality": "poor_match",
            "stage_decision": "consideration",
        },
    )

    result = aggregate_improvement_signals(days=7, company_id=None)
    assert result.get("corrected_responses", 0) >= 1
    signals = list(ImprovementSignal.objects.filter(issue_type="corrected_response"))
    pattern_keys = {s.pattern_key for s in signals}
    assert "objection_handling" in pattern_keys or "objection:price_too_high" in pattern_keys
    assert any("strategy:" in k or "objection:" in k or "stage:" in k for k in pattern_keys)


@pytest.mark.django_db
def test_generate_operator_recommendations():
    """generate_operator_recommendations returns list of dicts."""
    ImprovementSignal.objects.create(
        issue_type="escalation_reason",
        source_feature="support",
        pattern_key="angry_customer",
        frequency=5,
        recommended_action="Add FAQ for angry customers",
        review_status="pending",
    )
    recs = generate_operator_recommendations(limit=10)
    assert isinstance(recs, list)
    if recs:
        assert "issue_type" in recs[0]
        assert "recommended_action" in recs[0]
        assert "frequency" in recs[0]


# --- Multi-agent sales improvement insights tests ---


@pytest.mark.django_db
def test_aggregate_improvement_signals_includes_sales_counts():
    """aggregate_improvement_signals includes sales agent insight counts."""
    result = aggregate_improvement_signals(days=7, company_id=None)
    assert "repeated_fallback_reply" in result
    assert "low_confidence_recommendation" in result
    assert "objection_handling_failure" in result
    assert "weak_stage_advancement" in result
    assert "cold_to_hot_opportunity" in result
    assert "high_value_escaped_late" in result


@pytest.mark.django_db
def test_sales_insights_repeated_fallback_reply():
    """Repeated fallback replies are detected and aggregated."""
    from console.models import OrchestrationSnapshot

    ident = CustomerIdentity.objects.create(external_id="test-fallback-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-fb-1",
        response_produced="مرحباً! كيف يمكنني مساعدتك؟",
        mode="sales",
    )
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-fb-2",
        response_produced="Hello! How can I help you?",
        mode="sales",
    )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["repeated_fallback_reply"] >= 1
    signals = list(ImprovementSignal.objects.filter(issue_type="repeated_fallback_reply"))
    assert len(signals) >= 1
    assert any(s.pattern_key == "generic_opener" for s in signals)


@pytest.mark.django_db
def test_sales_insights_low_confidence_recommendation():
    """Low-confidence recommendations are detected and aggregated."""
    from console.models import OrchestrationSnapshot

    ident = CustomerIdentity.objects.create(external_id="test-lowconf-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-lc-1",
        mode="sales",
        scoring={"confidence": "low", "score": 50},
        intent={"primary": "project_inquiry"},
    )
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-lc-2",
        mode="sales",
        scoring={"confidence": 0.4, "score": 45},
        intent={"primary": "price_inquiry"},
    )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["low_confidence_recommendation"] >= 1
    signals = list(
        ImprovementSignal.objects.filter(issue_type="low_confidence_recommendation")
    )
    assert len(signals) >= 1


@pytest.mark.django_db
def test_sales_insights_objection_handling_failure():
    """Objection handling failures from ReinforcementSignal are aggregated."""
    from improvement.services.reinforcement_signals import record_reinforcement_signal

    ident = CustomerIdentity.objects.create(external_id="test-obj-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    record_reinforcement_signal(
        "objection_unresolved",
        conversation_id=conv.id,
        customer_id=cust.id,
        metadata={"objection_key": "price_too_high"},
    )
    record_reinforcement_signal(
        "objection_unresolved",
        conversation_id=conv.id,
        customer_id=cust.id,
        metadata={"objection_key": "location_concern"},
    )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["objection_handling_failure"] >= 1
    signals = list(
        ImprovementSignal.objects.filter(issue_type="objection_handling_failure")
    )
    assert len(signals) >= 1
    keys = {s.pattern_key for s in signals}
    assert "price_too_high" in keys or "location_concern" in keys


@pytest.mark.django_db
def test_sales_insights_weak_stage_advancement():
    """Conversations stuck in same stage for 3+ turns are detected."""
    from console.models import OrchestrationSnapshot

    ident = CustomerIdentity.objects.create(external_id="test-stage-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    for i in range(4):
        OrchestrationSnapshot.objects.create(
            conversation=conv,
            run_id=f"run-stage-{i}",
            journey_stage="awareness",
            mode="sales",
        )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["weak_stage_advancement"] >= 1
    signals = list(
        ImprovementSignal.objects.filter(issue_type="weak_stage_advancement")
    )
    assert len(signals) >= 1
    assert any(s.pattern_key == "awareness" for s in signals)


@pytest.mark.django_db
def test_sales_insights_cold_to_hot_opportunity():
    """Cold/nurture leads with visit intent are detected."""
    from console.models import OrchestrationSnapshot

    ident = CustomerIdentity.objects.create(external_id="test-cth-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-cth-1",
        mode="sales",
        scoring={"temperature": "cold", "score": 30},
        intent={"primary": "schedule_visit"},
    )
    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-cth-2",
        mode="sales",
        scoring={"temperature": "nurture"},
        intent={"primary": "project_inquiry_visit"},
    )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["cold_to_hot_opportunity"] >= 1
    signals = list(
        ImprovementSignal.objects.filter(issue_type="cold_to_hot_opportunity")
    )
    assert len(signals) >= 1


@pytest.mark.django_db
def test_sales_insights_high_value_escaped_late():
    """High-score leads that escalated are detected."""
    from console.models import OrchestrationSnapshot

    ident = CustomerIdentity.objects.create(external_id="test-hvel-1")
    cust = Customer.objects.create(identity=ident)
    conv = Conversation.objects.create(customer=cust, channel=SourceChannel.WEB)

    OrchestrationSnapshot.objects.create(
        conversation=conv,
        run_id="run-hvel-1",
        mode="sales",
        scoring={"score": 85, "confidence": "high"},
    )
    Escalation.objects.create(
        customer=cust,
        conversation=conv,
        reason=EscalationReason.COMPLEX_INQUIRY,
        status=EscalationStatus.OPEN,
    )

    from improvement.services.sales_agent_insights import aggregate_sales_agent_insights

    result = aggregate_sales_agent_insights(days=7, company_id=None)
    assert result["high_value_escaped_late"] >= 1
    signals = list(
        ImprovementSignal.objects.filter(issue_type="high_value_escaped_late")
    )
    assert len(signals) >= 1
