"""
Sales evaluation harness tests.
"""
import json
import pytest
from pathlib import Path

from evaluation.models import SalesEvalScenario, SalesEvalRun, SalesEvalResult
from evaluation.scoring import (
    score_intent,
    score_qualification_completeness,
    score_stage,
    score_objection_handling,
    score_next_step_usefulness,
    score_arabic_naturalness,
    score_repetition,
    compute_all_scores,
)
from evaluation.sales_eval_runner import run_sales_scenario, run_sales_evaluation


def test_score_intent_match():
    assert score_intent("project_inquiry", "project_inquiry") == 1.0
    assert score_intent("project_inquiry", "property_purchase") == 1.0  # alias
    assert score_intent("", "project_inquiry") == 0.0


def test_score_intent_no_expectation():
    assert score_intent("anything", "") == 1.0


def test_score_qualification_completeness():
    assert score_qualification_completeness({}, {}) == 1.0
    assert score_qualification_completeness(
        {"budget_max": 3000000, "location_preference": "المعادي"},
        {"budget_max": 3000000, "location_preference": "المعادي"},
    ) >= 0.9
    assert score_qualification_completeness(
        {"location_preference": "التجمع"},
        {"location_preference": "التجمع"},
    ) == 1.0


def test_score_stage():
    assert score_stage("consideration", "consideration") == 1.0
    assert score_stage("exploration", "consideration") == 0.8  # fuzzy
    assert score_stage("", "awareness") == 0.0


def test_score_objection_handling():
    resp = "فهمت قلقك تماماً. أسعارنا تعكس جودة البناء. يمكننا عرض خطط تقسيط."
    assert score_objection_handling("غالي", resp, "price_too_high", True) >= 0.8
    assert score_objection_handling("x", "short", "price_too_high") < 0.5


def test_score_next_step_usefulness():
    resp = "متى يناسبك للمعاينة؟ فريقنا جاهز."
    routing = {"recommended_cta": "propose_visit"}
    assert score_next_step_usefulness(resp, routing, "propose_visit") >= 0.7


def test_score_arabic_naturalness():
    resp = "أهلاً وسهلاً! يسعدني مساعدتك. تمام، هل تفضل شقة جاهزة؟"
    assert score_arabic_naturalness(resp, True) >= 0.6
    assert score_arabic_naturalness("How can I help?", True) < 0.5


def test_score_repetition():
    history = [
        {"role": "assistant", "content": "ما هي ميزانيتك التقريبية؟"},
        {"role": "user", "content": "3 مليون"},
        {"role": "assistant", "content": "ما هي ميزانيتك التقريبية؟"},  # repeated
    ]
    rep = score_repetition(history, "ما هي ميزانيتك التقريبية؟")
    assert rep > 0


def test_compute_all_scores():
    class FakeScenario:
        expected_intent = "project_inquiry"
        expected_intent_aliases = []
        expected_qualification = {}
        expected_stage = ""
        expected_objection_key = ""
        expected_next_action = ""
        expected_response_contains = []
        expected_response_excludes = []
        expected_match_criteria = {}
        messages = [{"role": "user", "content": "عايز شقة"}]

    actual = {
        "intent": "project_inquiry",
        "qualification": {},
        "journey_stage": "awareness",
        "routing": {},
        "recommendation_matches": [],
        "final_response": "أهلاً! يسعدني مساعدتك.",
        "policy_decision": {},
    }
    scores, failures = compute_all_scores(FakeScenario(), actual)
    assert scores.intent == 1.0
    assert isinstance(scores.to_dict(), dict)
    assert "intent" in scores.to_dict()


@pytest.mark.django_db
def test_sales_eval_scenario_model():
    s = SalesEvalScenario.objects.create(
        category="intent",
        name="TEST-001",
        messages=[{"role": "user", "content": "عايز شقة"}],
        expected_intent="project_inquiry",
    )
    assert s.id
    assert str(s).startswith("intent:")


@pytest.mark.django_db
def test_load_sales_eval_scenarios():
    from django.core.management import call_command
    from io import StringIO

    # Clear first
    SalesEvalScenario.objects.all().delete()
    out = StringIO()
    call_command("load_sales_eval_scenarios", "--clear", stdout=out)
    assert SalesEvalScenario.objects.count() >= 1
    s = SalesEvalScenario.objects.filter(category="intent").first()
    assert s is not None


@pytest.mark.django_db
def test_run_sales_eval_no_save():
    """Run without persisting - useful for CI."""
    SalesEvalScenario.objects.get_or_create(
        name="SE-TEST-MIN-EVAL",
        defaults={
            "category": "intent",
            "messages": [{"role": "user", "content": "مرحبا"}],
        },
    )
    out = run_sales_evaluation(use_llm=False, save=False)
    if out.get("error"):
        pytest.skip(out["error"])
    assert "run_id" in out
    assert "metrics" in out
    assert "total" in out
    assert out["total"] >= 1
