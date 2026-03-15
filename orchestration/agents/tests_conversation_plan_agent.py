"""
Tests for the Conversation Planning Agent.
Covers: incomplete lead, high-intent lead, support interruption.
Ensures plans are internal and never exposed to end users.
"""
import pytest
from orchestration.agents.base import AgentContext
from orchestration.agents.conversation_plan_agent import ConversationPlanAgent
from orchestration.agents.schemas import ConversationPlanAgentOutput
from orchestration.agents.registry import get_agent
from orchestration.agents import run_agent_pipeline


def _mk_ctx(
    message_text: str = "",
    intent_output: dict | None = None,
    qualification_output: dict | None = None,
    memory_output: dict | None = None,
    sales_strategy_output: dict | None = None,
    journey_stage_output: dict | None = None,
    persuasion_output: dict | None = None,
    response_mode: str | None = None,
) -> AgentContext:
    return AgentContext(
        run_id="test",
        message_text=message_text,
        conversation_history=[],
        identity_resolution={"matched": False},
        use_llm=False,
        intent_output=intent_output or {},
        qualification_output=qualification_output or {},
        memory_output=memory_output or {},
        sales_strategy_output=sales_strategy_output or {},
        journey_stage_output=journey_stage_output or {},
        persuasion_output=persuasion_output or {},
        response_mode=response_mode,
    )


def test_conversation_plan_agent_incomplete_lead():
    """Incomplete lead: has minimal qualification, plan shows what we need."""
    ctx = _mk_ctx(
        message_text="أريد شقة",
        intent_output={"primary": "property_search", "is_support": False},
        qualification_output={
            "budget_min": None,
            "budget_max": None,
            "location_preference": "",
            "missing_fields": ["budget", "location"],
            "lead_score": 30,
            "lead_temperature": "nurture",
        },
        sales_strategy_output={
            "objective": "Qualify budget to filter options",
            "recommended_cta": "ask_budget",
        },
        journey_stage_output={"next_sales_move": "Share value proposition and qualify budget/location"},
    )
    agent = ConversationPlanAgent()
    result = agent.run(ctx)
    assert result.success
    plan = ctx.conversation_plan_output
    assert plan is not None
    assert "what_we_know" in plan
    assert "what_we_still_need" in plan
    assert "sales_objective_now" in plan
    assert "best_next_question_or_suggestion" in plan
    # Incomplete: we still need budget, location
    assert "Budget" in plan["what_we_still_need"] or "budget" in str(plan["what_we_still_need"]).lower()
    assert "Location" in plan["what_we_still_need"] or "location" in str(plan["what_we_still_need"]).lower()
    assert plan["sales_objective_now"]


def test_conversation_plan_agent_high_intent_lead():
    """High-intent lead: has budget, location, plan shows what we know and conversion objective."""
    ctx = _mk_ctx(
        message_text="أريد حجز وحدة في المشروع",
        intent_output={"primary": "property_purchase", "is_support": False},
        qualification_output={
            "budget_min": "2000000",
            "budget_max": "3000000",
            "location_preference": "New Cairo",
            "project_preference": "مشروع X",
            "missing_fields": [],
            "lead_score": 85,
            "lead_temperature": "hot",
        },
        sales_strategy_output={
            "objective": "Schedule site visit",
            "recommended_cta": "propose_visit",
        },
        journey_stage_output={"next_sales_move": "Confirm visit slot and send directions"},
    )
    agent = ConversationPlanAgent()
    result = agent.run(ctx)
    assert result.success
    plan = ctx.conversation_plan_output
    assert plan is not None
    assert len(plan["what_we_know"]) >= 2
    assert any("Budget" in k or "2" in k or "2000000" in k for k in plan["what_we_know"])
    assert any("Location" in k or "New Cairo" in k for k in plan["what_we_know"])
    assert len(plan["what_we_still_need"]) == 0
    assert "visit" in plan["sales_objective_now"].lower() or "زيارة" in plan["sales_objective_now"]


def test_conversation_plan_agent_support_interruption():
    """Support interruption: is_support=True, plan prioritizes resolve issue."""
    ctx = _mk_ctx(
        message_text="أنا غاضب، لم أستلم عقدي بعد",
        intent_output={"primary": "contract_issue", "is_support": True},
        qualification_output={
            "budget_min": "2000000",
            "location_preference": "6th October",
            "missing_fields": ["bedrooms"],
        },
        sales_strategy_output={
            "objective": "Resolve support issue",
            "recommended_cta": "move_to_human",
        },
        response_mode="support",
    )
    agent = ConversationPlanAgent()
    result = agent.run(ctx)
    assert result.success
    plan = ctx.conversation_plan_output
    assert plan is not None
    assert "support" in plan["sales_objective_now"].lower() or "Resolve" in plan["sales_objective_now"]
    # Support path: what_we_still_need should be empty (we're not qualifying)
    assert plan["what_we_still_need"] == []


def test_conversation_plan_output_schema():
    """ConversationPlanAgentOutput schema round-trip and validation."""
    o = ConversationPlanAgentOutput(
        what_we_know=["Budget: 2M-3M", "Location: New Cairo"],
        what_we_still_need=["Bedroom count"],
        sales_objective_now="Schedule site visit",
        best_next_question_or_suggestion="ما هي ميزانيتك؟",
    )
    d = o.to_dict()
    assert d["what_we_know"] == ["Budget: 2M-3M", "Location: New Cairo"]
    assert d["what_we_still_need"] == ["Bedroom count"]
    assert d["sales_objective_now"] == "Schedule site visit"
    restored = ConversationPlanAgentOutput.from_dict(d)
    assert restored.what_we_know == o.what_we_know
    assert restored.best_next_question_or_suggestion == o.best_next_question_or_suggestion


def test_plan_not_exposed_in_draft_response():
    """Internal planning text must NOT appear in the final draft_response."""
    ctx = AgentContext(
        run_id="plan_hidden",
        message_text="عايز شقة في الشيخ زايد",
        conversation_history=[],
        identity_resolution={"matched": False},
        use_llm=False,
        qualification_override={"location_preference": "Sheikh Zayed"},
        response_mode="sales",
    )
    # Run full pipeline up to and including response_composer
    pipeline = [
        "intent", "lead_qualification", "memory", "retrieval",
        "sales_strategy", "persuasion", "journey_stage",
        "conversation_plan", "response_composer",
    ]
    updated_ctx, _ = run_agent_pipeline(pipeline, ctx)
    draft = (updated_ctx.response_composer_output or {}).get("reply_text", "") or (updated_ctx.response_composer_output or {}).get("draft_response", "")
    # Internal plan fields must not appear verbatim in user-facing response
    assert "what_we_know" not in draft
    assert "what_we_still_need" not in draft
    assert "sales_objective_now" not in draft
    assert "best_next_question_or_suggestion" not in draft
    assert "Current objective:" not in draft
    assert "Best next move:" not in draft


def test_conversation_plan_in_pipeline():
    """Conversation plan agent runs in pipeline and populates context."""
    ctx = AgentContext(
        run_id="pipeline_test",
        message_text="شقة بميزانية 3 مليون في المعادي",
        conversation_history=[],
        identity_resolution={"matched": False},
        use_llm=False,
        response_mode="sales",
    )
    pipeline = [
        "intent", "lead_qualification", "memory", "retrieval",
        "sales_strategy", "persuasion", "journey_stage",
        "conversation_plan", "response_composer",
    ]
    updated_ctx, _ = run_agent_pipeline(pipeline, ctx)
    assert updated_ctx.conversation_plan_output is not None
    plan = updated_ctx.conversation_plan_output
    assert "what_we_know" in plan
    assert "sales_objective_now" in plan
    assert "best_next_question_or_suggestion" in plan


def test_agent_registered():
    """Conversation plan agent is registered."""
    agent = get_agent("conversation_plan")
    assert agent is not None
    assert agent.name == "conversation_plan"
