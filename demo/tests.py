"""
Smoke tests for v0 pilot - ingestion, CRM, scoring, orchestration, UI.
Run: pytest demo/tests.py -v
"""
import csv
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_smoke_ingestion():
    """Ingestion pipeline loads and processes content."""
    from knowledge.ingestion import ingest_from_content
    from core.enums import DocumentType

    content = "Test content for smoke. سؤال عن المشاريع."
    doc = ingest_from_content(content, DocumentType.FAQ, "smoke", "Smoke FAQ")
    assert doc
    assert doc.title
    assert doc.status in ("parsed", "chunked", "embedded", "pending")


@pytest.mark.django_db
def test_smoke_crm_import(tmp_path):
    """CRM import accepts CSV and creates records."""
    from crm.services.import_service import import_crm_file

    csv_path = tmp_path / "smoke.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "crm_id", "name", "phone", "email", "source",
                "notes", "project_interest", "status",
            ],
        )
        w.writeheader()
        w.writerow({
            "crm_id": "SMOKE1",
            "name": "Smoke Lead",
            "phone": "+201012345678",
            "email": "smoke@test.local",
            "source": "web",
            "notes": "Test",
            "project_interest": "مشروع النخيل",
            "status": "new",
        })
    stats = import_crm_file(str(csv_path), dry_run=False)
    assert "imported" in stats or "error" not in str(stats).lower()


@pytest.mark.django_db
def test_smoke_scoring():
    """Scoring engine produces score and temperature."""
    from intelligence.services.scoring_engine import score_lead
    from intelligence.schemas import QualificationExtraction, IntentResult

    qual = QualificationExtraction(
        budget_min=2_000_000,
        budget_max=3_000_000,
        budget_clarity="explicit_range",
        location_preference="القاهرة الجديدة",
        urgency="soon",
        confidence="high",
    )
    intent = IntentResult(
        primary="property_purchase",
        confidence=0.9,
        is_support=False,
        is_spam=False,
        is_broker=False,
    )
    scoring = score_lead(qual, intent)
    assert scoring.score >= 0
    assert scoring.temperature in ("hot", "warm", "cold", "nurture")
    assert scoring.next_best_action


@pytest.mark.django_db
def test_smoke_orchestration():
    """Orchestration pipeline runs end-to-end."""
    from orchestration.orchestrator import run_orchestration
    from orchestration.states import RunStatus

    run = run_orchestration(
        "أبحث عن شقة في القاهرة الجديدة",
        external_id="smoke_eval",
        use_llm=False,
    )
    assert run.run_id
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)
    assert run.intent_result
    assert run.final_response


@pytest.mark.django_db
def test_smoke_ui_dashboard():
    """Console dashboard loads."""
    client = Client()
    url = reverse("console:dashboard")
    resp = client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_smoke_ui_conversations():
    """Conversations list loads."""
    client = Client()
    resp = client.get(reverse("console:conversations"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_smoke_health():
    """Health endpoint returns structured response."""
    from django.test import Client
    from django.urls import reverse
    client = Client()
    r = client.get("/health/db/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("check") == "db"


@pytest.mark.django_db
def test_smoke_ui_demo_eval():
    """Demo eval mode loads."""
    client = Client()
    resp = client.get(reverse("console:demo_eval"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_smoke_load_demo_scenarios():
    """load_demo_scenarios command runs."""
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    call_command("load_demo_scenarios", "--clear", stdout=out)
    assert "Loaded" in out.getvalue() or "scenarios" in out.getvalue().lower()


@pytest.mark.django_db
def test_smoke_eval_runner():
    """Eval runner can run a single scenario."""
    from demo.models import DemoScenario
    from demo.eval_runner import run_scenario

    scenario, _ = DemoScenario.objects.get_or_create(
        name="SMOKE",
        scenario_type="new_lead",
        defaults={
            "messages": [{"role": "user", "content": "أبحث عن شقة"}],
            "expected_intent": "project_inquiry",
            "expected_route": "sales",
        },
    )
    actual, failures, run_time = run_scenario(scenario, use_llm=False)
    assert "intent" in actual or "customer_type" in actual
    assert isinstance(failures, list)
    assert run_time >= 0
