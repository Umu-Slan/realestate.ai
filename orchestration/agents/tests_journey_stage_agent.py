"""
Tests for Buyer Journey Stage Agent.
Covers stage detection, confidence, stage_reasoning, and next_sales_move.
"""
import pytest

from orchestration.agents.journey_stage_agent import JourneyStageAgent
from orchestration.agents.base import AgentContext
from orchestration.agents.schemas import JourneyStageAgentOutput, JOURNEY_STAGES


def test_journey_stage_agent_awareness():
    """Cold inquiry without qualification -> awareness."""
    agent = JourneyStageAgent()
    ctx = AgentContext(
        run_id="t1",
        message_text="أريد شقة",
        conversation_history=[],
        intent_output={"primary": "project_inquiry"},
        qualification_output={"budget_min": None, "budget_max": None},
        memory_output={"customer_type_hint": "new_lead"},
        routing_output={"route": "sales", "customer_type": "new_lead"},
    )
    result = agent.run(ctx)
    assert result.success
    assert ctx.journey_stage_output
    out = JourneyStageAgentOutput.from_dict(ctx.journey_stage_output)
    assert out.stage == "awareness"
    assert 0 <= out.confidence <= 1
    assert isinstance(out.stage_reasoning, list)
    assert out.next_sales_move


def test_journey_stage_agent_consideration():
    """Price inquiry with budget -> consideration or shortlisting (both valid per detect_journey_stage)."""
    agent = JourneyStageAgent()
    ctx = AgentContext(
        run_id="t2",
        message_text="كم سعر الشقق؟",
        conversation_history=[],
        intent_output={"primary": "price_inquiry"},
        qualification_output={
            "budget_min": "2000000",
            "budget_max": "2500000",
            "location_preference": "New Cairo",
        },
        memory_output={"customer_type_hint": "new_lead"},
        routing_output={"route": "sales", "customer_type": "new_lead"},
    )
    result = agent.run(ctx)
    assert result.success
    out = JourneyStageAgentOutput.from_dict(ctx.journey_stage_output)
    assert out.stage in ("consideration", "shortlisting")
    assert out.confidence >= 0.6
    assert "qualified" in " ".join(out.stage_reasoning).lower() or "budget" in " ".join(out.stage_reasoning).lower()
    assert out.next_sales_move


def test_journey_stage_agent_visit_planning():
    """Schedule visit + qualified -> visit_planning."""
    agent = JourneyStageAgent()
    ctx = AgentContext(
        run_id="t3",
        message_text="أريد زيارة المشروع",
        conversation_history=[],
        intent_output={"primary": "schedule_visit"},
        qualification_output={
            "budget_min": "2000000",
            "location_preference": "New Cairo",
        },
        memory_output={"customer_type_hint": "new_lead"},
        routing_output={"route": "sales", "customer_type": "new_lead"},
    )
    result = agent.run(ctx)
    assert result.success
    out = JourneyStageAgentOutput.from_dict(ctx.journey_stage_output)
    assert out.stage == "visit_planning"
    assert out.next_sales_move


def test_journey_stage_agent_support_retention():
    """Support customer + support route -> support_retention."""
    agent = JourneyStageAgent()
    ctx = AgentContext(
        run_id="t4",
        message_text="متى القسط القادم؟",
        conversation_history=[],
        intent_output={"primary": "installment_inquiry"},
        qualification_output={},
        memory_output={"customer_type_hint": "support_customer"},
        routing_output={"route": "support", "customer_type": "support_customer"},
    )
    result = agent.run(ctx)
    assert result.success
    out = JourneyStageAgentOutput.from_dict(ctx.journey_stage_output)
    assert out.stage == "support_retention"
    assert "support" in out.next_sales_move.lower() or "resolve" in out.next_sales_move.lower()


def test_journey_stage_schema_output_fields():
    """Schema validates and normalizes output fields."""
    out = JourneyStageAgentOutput(
        stage="shortlisting",
        confidence=0.85,
        stage_reasoning=["intent=brochure_request", "qualified: budget, location"],
        next_sales_move="Share brochures and arrange site visit",
    )
    assert out.stage == "shortlisting"
    assert out.confidence == 0.85
    assert len(out.stage_reasoning) == 2
    d = out.to_dict()
    assert d["stage"] == "shortlisting"
    assert d["confidence"] == 0.85
    assert "stage_reasoning" in d
    assert "next_sales_move" in d


def test_journey_stage_schema_invalid_stage_fallback():
    """Invalid stage falls back to awareness."""
    out = JourneyStageAgentOutput(stage="invalid_stage", confidence=0.5)
    assert out.stage == "awareness"


def test_journey_stage_schema_confidence_clamped():
    """Confidence is clamped to [0, 1]."""
    out = JourneyStageAgentOutput(stage="consideration", confidence=1.5)
    assert out.confidence == 1.0
    out2 = JourneyStageAgentOutput(stage="awareness", confidence=-0.2)
    assert out2.confidence == 0.0


def test_journey_stage_agent_in_pipeline():
    """Journey stage agent runs in full pipeline and populates context."""
    from orchestration.agents import run_agent_pipeline
    from orchestration.agents.bootstrap import DEFAULT_AGENT_PIPELINE

    ctx = AgentContext(
        run_id="pipe_test",
        message_text="عايز أشوف شقق في المعادي بميزانية 3 مليون",
        conversation_history=[],
        identity_resolution={"matched": False},
        use_llm=False,
    )
    updated_ctx, results = run_agent_pipeline(DEFAULT_AGENT_PIPELINE, ctx, stop_on_failure=False)
    journey_results = [r for name, r in results if name == "journey_stage"]
    assert len(journey_results) == 1
    assert journey_results[0].success
    assert updated_ctx.journey_stage_output
    out = JourneyStageAgentOutput.from_dict(updated_ctx.journey_stage_output)
    assert out.stage in JOURNEY_STAGES
    assert out.confidence >= 0
    assert out.next_sales_move
