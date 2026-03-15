"""
End-to-end verification of the real estate AI pipeline.
Simulates 4 scenarios and verifies each pipeline step.

Unit-style (fast, no HTTP): TestScenario*Unit - run_orchestration only.
Full E2E (slower, with persistence): TestScenario* - HTTP + run_canonical_pipeline.

Run: pytest core/tests_e2e_scenarios.py -v --tb=short
Run unit only: pytest core/tests_e2e_scenarios.py -k Unit -v --tb=short
"""
import pytest
from django.test import Client


@pytest.fixture
def client_with_session():
    """Client with established session for demo persistence."""
    client = Client()
    client.post("/api/engines/sales/", {"message": "hi", "use_llm": False}, content_type="application/json")
    return client


def _post_sales(client, msg: str):
    return client.post("/api/engines/sales/", {"message": msg, "use_llm": False}, content_type="application/json")


def _post_support(client, msg: str, is_angry: bool = False):
    return client.post(
        "/api/engines/support/",
        {"message": msg, "is_angry": is_angry, "use_llm": False},
        content_type="application/json",
    )


def _post_recommend(client, qual: dict):
    return client.post("/api/engines/recommend/", {**qual, "use_llm": False}, content_type="application/json")


@pytest.mark.django_db
class TestScenario1NewLead:
    """Scenario 1: New lead - apartment Sheikh Zayed, installments, 3M budget."""

    def test_full_pipeline(self, client_with_session):
        """Intent, qualification, scoring, routing, response, persistence, audit."""
        client = client_with_session
        msg = "عايز شقة في الشيخ زايد بالتقسيط وميزانيتي 3 مليون"
        resp = _post_sales(client, msg)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert data["response"]

        from leads.models import LeadScore
        from conversations.models import Conversation, Message
        from audit.models import ActionLog

        conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").order_by("-id").first()
        assert conv, "Demo conversation should exist"
        msgs = list(Message.objects.filter(conversation=conv).order_by("created_at"))
        assert len(msgs) >= 2

        scores = LeadScore.objects.filter(customer_id=conv.customer_id).order_by("-created_at")[:1]
        assert scores.exists(), "LeadScore should be persisted for new lead"
        assert scores.first().score is not None

        logs = ActionLog.objects.filter(payload__run_id__isnull=False).order_by("-id")[:5]
        assert logs.count() >= 2, "Audit logs should exist for orchestration"


@pytest.mark.django_db
class TestScenario2Recommendation:
    """Scenario 2: Recommendation - investment project in Sheikh Zayed."""

    def test_full_pipeline(self, client_with_session):
        """Investment intent, recommendation engine, match reasoning, persistence, console."""
        client = client_with_session
        qual = {
            "location_preference": "الشيخ زايد",
            "purpose": "استثمار",
        }
        resp = _post_recommend(client, qual)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "matches" in data

        from console.models import OrchestrationSnapshot
        from conversations.models import Conversation

        conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").order_by("-id").first()
        assert conv
        snaps = OrchestrationSnapshot.objects.filter(conversation_id=conv.id)
        assert snaps.exists()


@pytest.mark.django_db
class TestScenario3Support:
    """Scenario 3: Support - reserved customer asking handover date."""

    def test_full_pipeline(self, client_with_session):
        """Support detection, category, SupportCase, SLA, persistence, console."""
        client = client_with_session
        msg = "أنا حاجز عندكم وعايز أعرف ميعاد الاستلام"
        resp = _post_support(client, msg)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data

        from support.models import SupportCase
        from conversations.models import Conversation
        from console.models import OrchestrationSnapshot

        conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").order_by("-id").first()
        assert conv
        cases = SupportCase.objects.filter(conversation_id=conv.id)
        assert cases.exists(), "SupportCase should be created for support route"
        case = cases.first()
        assert case.sla_bucket
        assert case.category

        snaps = OrchestrationSnapshot.objects.filter(conversation_id=conv.id)
        assert snaps.exists()


@pytest.mark.django_db
class TestScenario4Escalation:
    """Scenario 4: Escalation - upset customer, contract and price."""

    def test_full_pipeline(self, client_with_session):
        """Escalation detection, Escalation record, handoff summary, persistence."""
        client = client_with_session
        msg = "أنا متضايق جدًا ومحتاج رد نهائي على العقد والسعر"
        resp = _post_support(client, msg, is_angry=True)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data

        from support.models import Escalation
        from conversations.models import Conversation

        conv = Conversation.objects.filter(customer__identity__external_id__startswith="demo:").order_by("-id").first()
        assert conv
        escalations = Escalation.objects.filter(conversation_id=conv.id)
        assert escalations.exists(), "Escalation should be created when is_angry + support"
        esc = escalations.first()
        assert esc.handoff_summary
        assert esc.reason


# --- Unit-style pipeline verification (fast, no HTTP) ---


@pytest.mark.django_db
def test_scenario1_unit_new_lead():
    """Scenario 1 pipeline: intent, qualification, scoring, routing, response (no persistence)."""
    from orchestration.orchestrator import run_orchestration
    from orchestration.states import RunStatus

    msg = "عايز شقة في الشيخ زايد بالتقسيط وميزانيتي 3 مليون"
    run = run_orchestration(msg, external_id="e2e_s1", use_llm=False)
    assert run.run_id
    assert run.intent_result.get("primary")
    assert run.qualification
    assert run.scoring.get("score") is not None
    assert run.journey_stage
    assert run.routing.get("route")
    assert run.final_response
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)
    assert run.handoff_summary


@pytest.mark.django_db
def test_scenario2_unit_recommendation():
    """Scenario 2 pipeline: recommendation engine, match reasoning."""
    from orchestration.orchestrator import run_orchestration
    from orchestration.states import RunStatus

    content = "Recommend: location Sheikh Zayed, purpose investment"
    qual = {"location_preference": "الشيخ زايد", "purpose": "استثمار"}
    run = run_orchestration(
        content,
        external_id="e2e_s2",
        response_mode="recommendation",
        qualification_override=qual,
        use_llm=False,
        lang="ar",
    )
    assert run.run_id
    assert run.final_response
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)
    assert hasattr(run, "recommendation_matches")


@pytest.mark.django_db
def test_scenario3_unit_support_delivery_inquiry():
    """Scenario 3 pipeline: support detection, delivery_inquiry intent."""
    from orchestration.orchestrator import run_orchestration
    from intelligence.services.intent_classifier import classify_intent

    msg = "أنا حاجز عندكم وعايز أعرف ميعاد الاستلام"
    intent = classify_intent(msg, use_llm=False)
    primary = getattr(intent.primary, "value", str(intent.primary)) if intent.primary else ""
    assert primary in ("delivery_inquiry", "general_support", "other") or intent.is_support

    run = run_orchestration(msg, external_id="e2e_s3", response_mode="support", use_llm=False)
    assert run.run_id
    assert run.intent_result.get("is_support") or run.routing.get("route") in ("support", "support_escalation", "legal_handoff")
    assert run.final_response


@pytest.mark.django_db
def test_scenario4_unit_escalation():
    """Scenario 4 pipeline: escalation detection when is_angry + support."""
    from orchestration.orchestrator import run_orchestration

    msg = "أنا متضايق جدًا ومحتاج رد نهائي على العقد والسعر"
    run = run_orchestration(msg, external_id="e2e_s4", response_mode="support", is_angry=True, use_llm=False)
    assert run.run_id
    assert run.routing.get("escalation_ready") or run.escalation_flags
    assert run.handoff_summary
