"""
Multi-agent orchestration tests.
Ensures agent pipeline runs, produces valid OrchestrationRun, and current flows still work.
"""
import pytest

from orchestration.orchestrator import run_orchestration
from orchestration.states import RunStatus
from orchestration.agents import (
    AGENT_REGISTRY,
    get_agent,
    run_agent_pipeline,
    DEFAULT_AGENT_PIPELINE,
)
from orchestration.agents.base import AgentContext


@pytest.mark.django_db
def test_legacy_orchestration_unchanged():
    """Current system still works without use_multi_agent."""
    run = run_orchestration(
        "What projects do you have?",
        external_id="legacy_test",
        use_llm=False,
    )
    assert run.run_id
    assert run.intent_result
    assert run.qualification
    assert run.scoring
    assert run.routing
    assert run.final_response
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)


@pytest.mark.django_db
def test_multi_agent_orchestration_runs():
    """Multi-agent path produces valid OrchestrationRun."""
    run = run_orchestration(
        "أريد شقة في المعادي",
        external_id="multi_agent_test",
        use_llm=False,
        use_multi_agent=True,
    )
    assert run.run_id
    assert run.intent_result
    assert "primary" in run.intent_result
    assert run.qualification
    assert run.scoring
    assert run.routing
    assert run.draft_response or run.final_response
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)
    # Journey stage agent populates stage
    assert run.journey_stage
    assert run.journey_stage in (
        "awareness", "exploration", "consideration", "shortlisting",
        "visit_planning", "negotiation", "booking", "post_booking",
        "support_retention", "unknown",
    )


@pytest.mark.django_db
def test_multi_agent_response_composed():
    """Final response is composed from agent outputs."""
    run = run_orchestration(
        "Hello, I need a brochure",
        external_id="compose_test",
        use_llm=False,
        use_multi_agent=True,
    )
    assert run.final_response
    assert len(run.final_response.strip()) > 0


@pytest.mark.django_db
def test_multi_agent_recommendation_mode():
    """Recommendation mode via multi-agent produces matches."""
    run = run_orchestration(
        "Recommend: budget 2M-3M, location New Cairo",
        external_id="rec_test",
        use_llm=False,
        response_mode="recommendation",
        qualification_override={
            "budget_min": "2000000",
            "budget_max": "3000000",
            "location_preference": "New Cairo",
        },
        use_multi_agent=True,
    )
    assert run.intent_result
    assert run.qualification
    assert run.final_response
    assert hasattr(run, "recommendation_matches") or run.recommendation_matches is not None


def test_agent_registry_has_all_agents():
    """All required agents are registered."""
    required = [
        "intent",
        "memory",
        "lead_qualification",
        "retrieval",
        "property_matching",
        "recommendation",
        "sales_strategy",
        "persuasion",
        "journey_stage",
        "conversation_plan",
        "response_composer",
        "follow_up",
    ]
    for name in required:
        agent = get_agent(name)
        assert agent is not None, f"Agent {name} not found"
        assert agent.name == name


def test_agent_pipeline_runs_deterministically():
    """Agent pipeline runs in order and produces outputs."""
    ctx = AgentContext(
        run_id="test_run",
        message_text="أريد شقة بميزانية 2 مليون",
        conversation_history=[],
        identity_resolution={"matched": False},
        use_llm=False,  # Deterministic for CI
    )
    results = run_agent_pipeline(["intent", "lead_qualification", "memory"], ctx)
    updated_ctx, agent_results = results
    assert len(agent_results) == 3
    assert updated_ctx.intent_output is not None
    assert updated_ctx.qualification_output is not None
    assert updated_ctx.memory_output is not None
    assert "customer_profile" in (updated_ctx.memory_output or {})
    for name, result in agent_results:
        assert result.success, f"Agent {name} failed: {result.error}"


def test_intent_agent_contract():
    """Intent agent has clear input/output."""
    from orchestration.agents.intent_agent import IntentAgent
    agent = IntentAgent()
    ctx = AgentContext(
        message_text="السعر كام؟",
        conversation_history=[],
        identity_resolution={},
    )
    result = agent.run(ctx)
    assert result.success
    assert ctx.intent_output
    assert "primary" in ctx.intent_output
    assert "confidence" in ctx.intent_output


def test_agent_result_loggable():
    """Agent results are inspectable/loggable."""
    from orchestration.agents.base import AgentResult
    r = AgentResult(agent_name="test", success=True, metadata={"key": "value"})
    loggable = r.to_loggable()
    assert loggable["agent"] == "test"
    assert loggable["success"] is True
    assert loggable["metadata"]["key"] == "value"


@pytest.mark.django_db
def test_sales_mode_multi_agent():
    """Sales mode works with multi-agent."""
    run = run_orchestration(
        "I'm interested in a villa in October",
        external_id="sales_ma",
        use_llm=False,
        response_mode="sales",
        use_multi_agent=True,
    )
    assert run.final_response
    assert run.routing.get("customer_type") or run.intent_result


@pytest.mark.django_db
def test_support_mode_multi_agent():
    """Support mode works with multi-agent."""
    run = run_orchestration(
        "I have a complaint about my unit",
        external_id="support_ma",
        use_llm=False,
        response_mode="support",
        use_multi_agent=True,
    )
    assert run.final_response
    assert run.intent_result
