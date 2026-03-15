"""
Tests for Sales Strategy Agent.
Covers: strategy, objective, persuasive_angle, recommended_cta, anti-repetition.
"""
import pytest
from unittest.mock import MagicMock

from orchestration.agents.sales_strategy_agent import (
    SalesStrategyAgent,
    _compute_recommended_cta,
    _recently_asked,
    PERSUASIVE_ANGLES,
    OBJECTIVES,
)
from orchestration.agents.schemas import SalesStrategyAgentOutput, SALES_CTA_OPTIONS
from orchestration.agents.base import AgentContext


def test_recently_asked_budget():
    """Detect when we recently asked for budget."""
    history = [
        {"role": "user", "content": "مرحبا"},
        {"role": "assistant", "content": "ما هي ميزانيتك التقريبية؟"},
    ]
    assert _recently_asked(history, "budget") is True


def test_recently_asked_location():
    """Detect when we recently asked for location."""
    history = [{"role": "assistant", "content": "أين تفضل المنطقة؟"}]
    assert _recently_asked(history, "location") is True


def test_recently_asked_not_recent():
    """No recent ask when user message."""
    history = [{"role": "user", "content": "ميزانيتي 3 مليون"}]
    assert _recently_asked(history, "budget") is False


def test_compute_cta_objection():
    """Objection -> address_objection."""
    cta = _compute_recommended_cta(
        intent={},
        qualification={},
        routing={},
        next_act_action="ask_budget",
        objection_key="price_too_high",
        temperature="warm",
        score=50,
        buyer_stage="consideration",
        has_recommendations=False,
        conversation_history=[],
    )
    assert cta == "address_objection"


def test_compute_cta_escalation():
    """Escalation ready -> move_to_human."""
    cta = _compute_recommended_cta(
        intent={},
        qualification={},
        routing={"escalation_ready": True},
        next_act_action="ask_budget",
        objection_key=None,
        temperature="warm",
        score=50,
        buyer_stage="",
        has_recommendations=False,
        conversation_history=[],
    )
    assert cta == "move_to_human"


def test_compute_cta_visit_intent():
    """Visit intent -> propose_visit."""
    cta = _compute_recommended_cta(
        intent={"primary": "schedule_visit"},
        qualification={},
        routing={},
        next_act_action="nurture_content",
        objection_key=None,
        temperature="warm",
        score=60,
        buyer_stage="",
        has_recommendations=True,
        conversation_history=[],
    )
    assert cta == "propose_visit"


def test_compute_cta_anti_repetition_budget():
    """Avoid re-asking budget when recently asked."""
    history = [{"role": "assistant", "content": "ما هي ميزانيتك؟"}]
    cta = _compute_recommended_cta(
        intent={},
        qualification={"missing_fields": ["budget", "location"]},
        routing={},
        next_act_action="ask_budget",
        objection_key=None,
        temperature="warm",
        score=40,
        buyer_stage="",
        has_recommendations=False,
        conversation_history=history,
    )
    assert cta in ("ask_location", "nurture")


def test_persuasive_angles_cover_all_ctas():
    """All CTAs have persuasive angles."""
    for cta in SALES_CTA_OPTIONS:
        assert cta in PERSUASIVE_ANGLES
        assert len(PERSUASIVE_ANGLES[cta]) > 10


def test_objectives_cover_all_ctas():
    """All CTAs have objectives."""
    for cta in SALES_CTA_OPTIONS:
        assert cta in OBJECTIVES


def test_sales_strategy_agent_returns_cta():
    """Agent populates strategy, objective, persuasive_angle, recommended_cta."""
    ctx = AgentContext(
        run_id="t1",
        message_text="أريد شقة في المعادي",
        conversation_history=[],
        intent_output={"primary": "project_inquiry", "stage_hint": "consideration"},
        qualification_output={
            "budget_min": "2000000",
            "budget_max": "3000000",
            "location_preference": "Maadi",
            "missing_fields": [],
            "lead_score": 65,
            "lead_temperature": "warm",
        },
        memory_output={"customer_type_hint": "new_lead"},
        retrieval_output={"has_verified_pricing": True},
        property_matching_output={"matches": [{"project_id": 1, "project_name": "X"}]},
    )
    agent = SalesStrategyAgent()
    result = agent.run(ctx)
    assert result.success
    out = ctx.sales_strategy_output
    assert "recommended_cta" in out
    assert out["recommended_cta"] in SALES_CTA_OPTIONS
    assert "strategy" in out
    assert "objective" in out
    assert "persuasive_angle" in out
