"""
Tests for Follow-up Agent.
Covers: gentle_reminder, alternative_recommendation, visit_prompt, value_based_follow_up.
Ensures structured records, no auto-send.
"""
import pytest
from orchestration.agents.base import AgentContext
from orchestration.agents.follow_up_agent import FollowUpAgent
from orchestration.agents.schemas import FollowUpAgentOutput
from orchestration.agents.registry import get_agent
from engines.follow_up_engine import (
    generate_follow_up_recommendations,
    _select_follow_up_type,
    FOLLOW_UP_TYPES,
)


def test_follow_up_agent_gentle_reminder():
    """Early-stage, low score -> gentle_reminder."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "awareness",
            "lead_score": 30,
            "last_discussed_projects": [],
            "time_since_last_interaction_hours": 24,
            "lead_ref": "lead_123",
        },
        lang="ar",
    )
    agent = FollowUpAgent()
    result = agent.run(ctx)
    assert result.success
    out = ctx.follow_up_output or {}
    recs = out.get("recommendations", [])
    assert len(recs) >= 1
    assert recs[0]["type"] == "gentle_reminder"
    assert "أهلاً" in recs[0]["message_text"] or "مرحباً" in recs[0]["message_text"]
    assert out.get("auto_send_enabled") is False


def test_follow_up_agent_visit_prompt():
    """Visit planning + hot lead + discussed projects -> visit_prompt."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "visit_planning",
            "lead_score": 75,
            "last_discussed_projects": ["مشروع X", "مشروع Y"],
            "time_since_last_interaction_hours": 36,
            "lead_ref": "lead_456",
        },
        lang="ar",
    )
    agent = FollowUpAgent()
    result = agent.run(ctx)
    assert result.success
    recs = (ctx.follow_up_output or {}).get("recommendations", [])
    assert len(recs) >= 1
    assert recs[0]["type"] == "visit_prompt"
    assert "زيارة" in recs[0]["message_text"] or "معاينة" in recs[0]["message_text"]


def test_follow_up_agent_alternative_recommendation():
    """Consideration + projects + long silence -> alternative_recommendation."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "consideration",
            "lead_score": 55,
            "last_discussed_projects": ["مشروع A"],
            "time_since_last_interaction_hours": 80,
            "lead_ref": "lead_789",
        },
        lang="ar",
    )
    agent = FollowUpAgent()
    result = agent.run(ctx)
    assert result.success
    recs = (ctx.follow_up_output or {}).get("recommendations", [])
    assert len(recs) >= 1
    assert recs[0]["type"] == "alternative_recommendation"


def test_follow_up_agent_value_based():
    """Hot lead + 48h+ silence -> value_based_follow_up."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "exploration",
            "lead_score": 60,
            "last_discussed_projects": [],
            "time_since_last_interaction_hours": 52,
            "lead_ref": "lead_999",
        },
        lang="ar",
    )
    agent = FollowUpAgent()
    result = agent.run(ctx)
    assert result.success
    recs = (ctx.follow_up_output or {}).get("recommendations", [])
    assert len(recs) >= 1
    assert recs[0]["type"] == "value_based_follow_up"


def test_follow_up_output_structured_records():
    """Recommendations are structured and JSON-serializable."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "shortlisting",
            "lead_score": 70,
            "last_discussed_projects": ["Project Alpha"],
            "time_since_last_interaction_hours": 24,
            "lead_ref": "ext_001",
        },
    )
    agent = FollowUpAgent()
    agent.run(ctx)
    out = ctx.follow_up_output or {}
    recs = out.get("recommendations", [])
    assert recs
    r = recs[0]
    assert "type" in r
    assert r["type"] in FOLLOW_UP_TYPES
    assert "message_text" in r
    assert "reasoning" in r
    assert "priority" in r
    assert "lead_ref" in r
    assert "time_since_last_hours" in r


def test_follow_up_never_auto_send():
    """auto_send_enabled is always False."""
    ctx = AgentContext(
        run_id="test",
        follow_up_input={
            "buyer_stage": "consideration",
            "lead_score": 80,
            "last_discussed_projects": ["X"],
            "time_since_last_interaction_hours": 10,
            "lead_ref": "x",
        },
    )
    agent = FollowUpAgent()
    agent.run(ctx)
    assert (ctx.follow_up_output or {}).get("auto_send_enabled") is False


def test_select_follow_up_type_visit_prompt():
    """Selection logic: visit_planning + score + projects -> visit_prompt."""
    t, r = _select_follow_up_type(
        buyer_stage="visit_planning",
        lead_score=70,
        last_projects=["P1"],
        time_since_last_hours=24,
    )
    assert t == "visit_prompt"


def test_select_follow_up_type_gentle_default():
    """Selection logic: cold lead -> gentle_reminder."""
    t, r = _select_follow_up_type(
        buyer_stage="awareness",
        lead_score=20,
        last_projects=[],
        time_since_last_hours=12,
    )
    assert t == "gentle_reminder"


def test_follow_up_schema_roundtrip():
    """FollowUpAgentOutput schema round-trip."""
    o = FollowUpAgentOutput(
        recommendations=[
            {"type": "gentle_reminder", "message_text": "أهلاً!", "priority": 50},
        ],
        auto_send_enabled=False,
        lead_ref="lead_1",
    )
    d = o.to_dict()
    assert d["auto_send_enabled"] is False
    assert len(d["recommendations"]) == 1
    restored = FollowUpAgentOutput.from_dict(d)
    assert restored.lead_ref == o.lead_ref


def test_follow_up_agent_registered():
    """Follow-up agent is registered."""
    agent = get_agent("follow_up")
    assert agent is not None
    assert agent.name == "follow_up"


def test_follow_up_messages_short_and_natural():
    """Generated messages are short and natural (no template bloat)."""
    recs = generate_follow_up_recommendations(
        buyer_stage="awareness",
        lead_score=40,
        last_discussed_projects=[],
        time_since_last_interaction_hours=48,
        lang="ar",
    )
    assert recs
    msg = recs[0].message_text
    assert len(msg) <= 250
    assert msg.strip()


def test_run_follow_up_service():
    """Orchestration follow-up service returns structured output."""
    from orchestration.follow_up_service import run_follow_up_for_lead

    out = run_follow_up_for_lead(
        buyer_stage="consideration",
        lead_score=65,
        last_discussed_projects=["مشروع X"],
        time_since_last_interaction_hours=48,
        lead_ref="svc_test",
        lang="ar",
    )
    assert "recommendations" in out
    assert out.get("auto_send_enabled") is False
    recs = out.get("recommendations", [])
    assert recs
    assert "type" in recs[0]
    assert "message_text" in recs[0]
