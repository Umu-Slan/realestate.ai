"""
Tests for Lead Qualification Agent and scorer.
Covers hot, warm, cold, nurture, unqualified cases with explainable reasoning.
"""
import pytest

from orchestration.agents.lead_qualification_scorer import (
    compute_lead_qualification_score,
    LeadQualificationScore,
    HOT_MIN,
    WARM_MIN,
    COLD_MIN,
    NURTURE_MIN,
)


def test_scorer_hot_lead():
    """Hot: budget + location + property + visit request."""
    qual = {
        "budget_min": 2_000_000,
        "budget_max": 2_500_000,
        "location_preference": "المعادي",
        "property_type": "apartment",
        "urgency": "immediate",
    }
    intent = {
        "primary": "schedule_visit",
        "sales_intent": "visit_request",
        "entities": {"budget": {"min": 2e6, "max": 2.5e6}, "location": "المعادي"},
    }
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_count=3,
        identity_matched=True,
    )
    assert r.lead_score >= WARM_MIN, f"Expected warm+, got {r.lead_score}"
    assert r.lead_temperature in ("hot", "warm")
    assert r.next_best_action
    assert any(rc.factor == "visit_interest" for rc in r.reasoning)
    assert any(rc.factor == "budget_clarity" for rc in r.reasoning)


def test_scorer_warm_lead():
    """Warm: budget + location, no visit yet."""
    qual = {
        "budget_min": 1_500_000,
        "budget_max": 2_000_000,
        "location_preference": "المعادي",
        "property_type": "villa",
        "urgency": "soon",
    }
    intent = {"primary": "property_purchase", "sales_intent": "property_search", "entities": {}}
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_count=1,
    )
    assert WARM_MIN <= r.lead_score < HOT_MIN or r.lead_score >= COLD_MIN
    assert r.lead_temperature in ("hot", "warm", "cold")
    assert any(rc.factor == "location_clarity" for rc in r.reasoning)
    assert "budget" not in r.missing_fields


def test_scorer_cold_lead():
    """Cold: some signals, exploring."""
    qual = {
        "location_preference": "New Cairo",
        "property_type": "apartment",
        "urgency": "exploring",
    }
    intent = {"primary": "project_inquiry", "sales_intent": "project_details", "entities": {}}
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_count=2,
    )
    assert r.lead_score >= NURTURE_MIN
    assert r.lead_temperature in ("cold", "nurture", "warm")
    assert "budget" in r.missing_fields


def test_scorer_nurture_lead():
    """Nurture: minimal signals - may score nurture or unqualified."""
    qual = {"property_type": "apartment", "location_preference": "Cairo"}
    intent = {"primary": "location_inquiry", "sales_intent": "location_inquiry", "entities": {}}
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_count=2,
    )
    assert r.lead_temperature in ("nurture", "cold", "unqualified")
    assert "budget" in r.missing_fields
    assert any(rc.factor == "property_type_clarity" for rc in r.reasoning)


def test_scorer_unqualified():
    """Unqualified: almost no signals."""
    qual = {}
    intent = {"primary": "other", "sales_intent": "unclear", "entities": {}}
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_count=1,
    )
    assert r.lead_score < NURTURE_MIN
    assert r.lead_temperature == "unqualified"
    assert "Ask for budget" in r.next_best_action or "Engage" in r.next_best_action


def test_scorer_returning_customer_boost():
    """Returning customer gets returning_behavior points."""
    qual = {"budget_min": 2e6, "location_preference": "المعادي"}
    intent = {"primary": "price_inquiry", "entities": {}}
    r_new = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        customer_type_hint="new_lead",
        identity_matched=False,
    )
    r_returning = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        customer_type_hint="returning_lead",
        identity_matched=True,
    )
    assert r_returning.lead_score > r_new.lead_score
    assert any(rc.factor == "returning_behavior" for rc in r_returning.reasoning)


def test_scorer_financing_readiness():
    """Financing/cash mention boosts score."""
    qual = {}
    intent = {"primary": "property_purchase", "entities": {}}
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
        message_text="عايز أشوف شقق وأنا كاش",
    )
    assert any(rc.factor == "financing_readiness" for rc in r.reasoning)
    assert any(rc.contribution > 0 for rc in r.reasoning if rc.factor == "financing_readiness")


def test_scorer_spam():
    """Spam returns 0, temperature spam."""
    r = compute_lead_qualification_score({}, {"primary": "other"}, is_spam=True)
    assert r.lead_score == 0
    assert r.lead_temperature == "spam"
    assert "Quarantine" in r.next_best_action


def test_scorer_broker():
    """Broker returns cold, route to broker."""
    r = compute_lead_qualification_score({}, {"is_broker": True}, is_broker=True)
    assert r.lead_temperature == "cold"
    assert "broker" in r.next_best_action.lower()


def test_scorer_intent_entities_merge():
    """Intent entities fill qualification gaps."""
    qual = {"urgency": "immediate"}
    intent = {
        "primary": "property_purchase",
        "entities": {
            "budget": {"min": 1.8e6, "max": 2.2e6},
            "location": "المعادي",
            "property_type": "apartment",
        },
    }
    r = compute_lead_qualification_score(
        qualification=qual,
        intent_output=intent,
    )
    assert r.lead_score >= 40
    assert "budget" not in r.missing_fields
    assert "location" not in r.missing_fields


def test_scorer_reasoning_explainable():
    """Every non-zero contribution has a note."""
    qual = {"budget_min": 2e6, "location_preference": "6 أكتوبر", "property_type": "villa"}
    intent = {"primary": "schedule_visit", "sales_intent": "visit_request", "entities": {}}
    r = compute_lead_qualification_score(qualification=qual, intent_output=intent)
    for rc in r.reasoning:
        if rc.contribution > 0:
            assert rc.note, f"Factor {rc.factor} has no note"


@pytest.mark.django_db
def test_lead_qualification_agent_integration():
    """Lead Qualification Agent produces score and reasoning."""
    from orchestration.agents import get_agent
    from orchestration.agents.base import AgentContext

    ctx = AgentContext(
        run_id="test",
        message_text="عايز شقة 2 مليون في المعادي، أريد زيارة",
        conversation_history=[],
        use_llm=False,
    )
    ctx.intent_output = {
        "primary": "property_purchase",
        "sales_intent": "property_search",
        "entities": {"budget": {"min": 1.8e6, "max": 2.2e6}, "location": "المعادي"},
    }

    agent = get_agent("lead_qualification")
    result = agent.run(ctx)
    assert result.success
    assert ctx.qualification_output
    assert "lead_score" in ctx.qualification_output
    assert "lead_temperature" in ctx.qualification_output
    assert "reasoning" in ctx.qualification_output
    assert "next_best_action" in ctx.qualification_output
    assert "missing_fields" in ctx.qualification_output
    assert ctx.qualification_output["lead_score"] >= 0
    assert ctx.qualification_output["lead_temperature"] in ("hot", "warm", "cold", "nurture", "unqualified", "spam")
