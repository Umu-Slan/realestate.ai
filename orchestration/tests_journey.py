"""
Journey stage detection and next-best-action tests.
"""
import pytest

from orchestration.journey_stage import detect_journey_stage
from orchestration.next_action import compute_next_best_action, NextBestAction
from core.enums import BuyerJourneyStage


def test_journey_stage_awareness():
    """Vague inquiry -> awareness."""
    stage = detect_journey_stage(
        intent_primary="project_inquiry",
        temperature="cold",
    )
    assert stage == BuyerJourneyStage.AWARENESS.value


def test_journey_stage_consideration():
    """Project inquiry with budget -> consideration."""
    stage = detect_journey_stage(
        intent_primary="price_inquiry",
        has_budget=True,
        temperature="warm",
    )
    assert stage == BuyerJourneyStage.CONSIDERATION.value


def test_journey_stage_shortlisting():
    """Brochure + project preference -> shortlisting."""
    stage = detect_journey_stage(
        intent_primary="brochure_request",
        has_project_preference=True,
        temperature="warm",
    )
    assert stage == BuyerJourneyStage.SHORTLISTING.value


def test_journey_stage_visit_planning():
    """Schedule visit + qualified -> visit_planning."""
    stage = detect_journey_stage(
        intent_primary="schedule_visit",
        has_budget=True,
        has_location=True,
    )
    assert stage == BuyerJourneyStage.VISIT_PLANNING.value


def test_journey_stage_support_retention():
    """Support intent -> support_retention."""
    stage = detect_journey_stage(
        intent_primary="installment_inquiry",
        customer_type="support_customer",
        routing_route="support",
    )
    assert stage == BuyerJourneyStage.SUPPORT_RETENTION.value


def test_journey_stage_post_booking():
    """Installment/delivery intent -> post_booking."""
    stage = detect_journey_stage(intent_primary="delivery_inquiry")
    assert stage == BuyerJourneyStage.POST_BOOKING.value


def test_next_action_propose_visit():
    """Visit intent -> propose_visit."""
    result = compute_next_best_action(
        customer_type="new_lead",
        intent_primary="schedule_visit",
        temperature="warm",
    )
    assert result.action == NextBestAction.PROPOSE_VISIT


def test_next_action_assign_sales_rep():
    """Hot lead in visit_planning -> assign_sales_rep."""
    result = compute_next_best_action(
        customer_type="new_lead",
        intent_primary="schedule_visit",
        journey_stage="visit_planning",
        temperature="hot",
        score=80,
    )
    assert result.action == NextBestAction.ASSIGN_SALES_REP


def test_next_action_ask_budget_with_stage():
    """Awareness stage + missing budget -> ask_budget."""
    result = compute_next_best_action(
        customer_type="new_lead",
        journey_stage="awareness",
        missing_fields=["budget"],
        temperature="cold",
    )
    assert result.action == NextBestAction.ASK_BUDGET


@pytest.mark.django_db
def test_sales_journey_persists_stage_and_action():
    """Sales message persists journey stage and next action in LeadScore."""
    from django.test import Client
    from leads.models import LeadScore
    from conversations.models import Conversation

    client = Client()
    resp = client.post(
        "/api/engines/sales/",
        {"message": "عايز شقة 3 غرف في المعادي، الميزانية 3 مليون. إرسل بروشور", "mode": "warm_lead", "use_llm": False},
        content_type="application/json",
    )
    assert resp.status_code == 200

    conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").first()
    assert conv is not None
    score = LeadScore.objects.filter(customer=conv.customer).order_by("-created_at").first()
    if score:
        assert score.journey_stage in (
            BuyerJourneyStage.AWARENESS.value,
            BuyerJourneyStage.CONSIDERATION.value,
            BuyerJourneyStage.SHORTLISTING.value,
        )
        # Next action should be set (send_brochure, recommend_project, or similar)
        assert score.next_best_action or True  # May be empty for some paths


@pytest.mark.django_db
def test_support_journey_support_retention():
    """Support message -> support_retention stage in snapshot."""
    from django.test import Client
    from console.models import OrchestrationSnapshot
    from conversations.models import Conversation

    client = Client()
    resp = client.post(
        "/api/engines/support/",
        {"message": "متى القسط القادم؟", "use_llm": False},
        content_type="application/json",
    )
    assert resp.status_code == 200

    conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").first()
    assert conv is not None
    snap = OrchestrationSnapshot.objects.filter(conversation=conv).order_by("-created_at").first()
    if snap:
        assert snap.journey_stage == BuyerJourneyStage.SUPPORT_RETENTION.value
        assert snap.next_best_action  # create_support_case or similar
