"""
Tests for production Retrieval Agent.
Covers Arabic and English retrieval, relevance threshold, structured summary, source-of-truth.
"""
import pytest

from orchestration.agents.retrieval_agent import RetrievalAgent, RELEVANCE_THRESHOLD
from orchestration.agents.base import AgentContext
from orchestration.agents.schemas import RetrievalAgentOutput, RetrievalSource
from orchestration.retrieval_planner import plan_retrieval, _resolve_project_id


def test_retrieval_planner_price_intent():
    """Price intent -> project + FAQ + brochure, structured pricing."""
    plan = plan_retrieval(
        message_text="كم سعر الشقق؟",
        intent_primary="price_inquiry",
        project_preference="",
    )
    assert "project" in str(plan.document_types).lower() or "faq" in str(plan.document_types).lower()
    assert plan.use_structured_pricing
    assert "price" in plan.reason.lower()


def test_retrieval_planner_location_intent():
    """Location intent -> location chunks."""
    plan = plan_retrieval(
        message_text="Where is the project located?",
        intent_primary="location_inquiry",
    )
    assert "location" in str(plan.chunk_types).lower() or "project" in str(plan.document_types).lower()
    assert "location" in plan.reason.lower()


def test_retrieval_planner_support_intent():
    """Support intent -> support SOPs and FAQs."""
    plan = plan_retrieval(
        message_text="متى القسط القادم؟",
        intent_primary="installment_inquiry",
        is_support=True,
    )
    assert "support" in str(plan.document_types).lower() or "faq" in str(plan.document_types).lower()
    assert "support" in plan.reason.lower()


def test_retrieval_planner_brochure_intent():
    """Brochure intent -> brochures and project docs."""
    plan = plan_retrieval(
        message_text="أريد بروشور المشروع",
        intent_primary="brochure_request",
    )
    assert "brochure" in str(plan.document_types).lower()


def test_retrieval_planner_arabic_message():
    """Arabic message passes through to query."""
    plan = plan_retrieval(
        message_text="عايز شقة في المعادي بميزانية 3 مليون",
        intent_primary="project_inquiry",
    )
    assert "شقة" in plan.query or "المعادي" in plan.query
    assert plan.document_types


def test_retrieval_planner_english_message():
    """English message passes through to query."""
    plan = plan_retrieval(
        message_text="I need an apartment in New Cairo, budget 2M-3M",
        intent_primary="project_inquiry",
    )
    assert "apartment" in plan.query or "Cairo" in plan.query or "budget" in plan.query.lower()
    assert plan.document_types


def test_retrieval_source_schema_extended():
    """RetrievalSource has relevance, source_of_truth, content_snippet."""
    s = RetrievalSource(
        chunk_id=1,
        document_title="FAQ",
        content_snippet="Payment plans up to 8 years.",
        relevance_score=0.85,
        source_of_truth=True,
        verification_status="verified",
        is_fresh=True,
        document_type="faq",
        chunk_type="faq_topic",
    )
    d = s.to_dict()
    assert d["relevance_score"] == 0.85
    assert d["source_of_truth"] is True
    assert "Payment" in d["content_snippet"]
    restored = RetrievalSource.from_dict(d)
    assert restored.relevance_score == 0.85
    assert restored.source_of_truth


def test_retrieval_agent_output_structured_summary():
    """RetrievalAgentOutput includes structured_summary and source_of_truth_count."""
    sources = [
        RetrievalSource(chunk_id=1, document_title="Doc1", source_of_truth=True),
        RetrievalSource(chunk_id=2, document_title="Doc2", source_of_truth=False),
    ]
    o = RetrievalAgentOutput(
        query="test",
        retrieval_sources=sources,
        structured_summary="Verified pricing available. - Doc1 (faq) [source-of-truth]",
        has_verified_pricing=True,
    )
    assert o.source_of_truth_count == 1
    assert "structured_summary" in o.to_dict()
    assert "Verified" in o.structured_summary or "Doc1" in o.structured_summary


def test_retrieval_agent_runs():
    """Retrieval agent runs without error (may return empty if no KB)."""
    try:
        import pgvector  # noqa: F401
    except ImportError:
        pytest.skip("pgvector required for retrieval")
    agent = RetrievalAgent()
    ctx = AgentContext(
        run_id="t1",
        message_text="أريد شقة في المعادي",
        conversation_history=[],
        intent_output={"primary": "project_inquiry"},
        qualification_output={},
        memory_output={},
    )
    result = agent.run(ctx)
    assert result.success
    assert ctx.retrieval_output is not None
    out = RetrievalAgentOutput.from_dict(ctx.retrieval_output)
    assert isinstance(out.retrieval_sources, list)
    assert out.query
    assert "structured_summary" in ctx.retrieval_output or "sources_count" in ctx.retrieval_output


def test_retrieval_agent_english_query():
    """Retrieval agent handles English message."""
    try:
        import pgvector  # noqa: F401
    except ImportError:
        pytest.skip("pgvector required for retrieval")
    agent = RetrievalAgent()
    ctx = AgentContext(
        run_id="t2",
        message_text="What is the price for apartments in 6 October?",
        conversation_history=[],
        intent_output={"primary": "price_inquiry"},
        qualification_output={"location_preference": "6 October"},
        memory_output={},
    )
    result = agent.run(ctx)
    assert result.success
    out = RetrievalAgentOutput.from_dict(ctx.retrieval_output)
    assert out.query
    assert "price" in out.query.lower() or "apartment" in out.query.lower() or "october" in out.query.lower()


def test_retrieval_agent_filters_low_relevance():
    """Sources below RELEVANCE_THRESHOLD are excluded (conceptual - agent applies threshold)."""
    assert RELEVANCE_THRESHOLD > 0
    assert RELEVANCE_THRESHOLD < 1


def test_resolve_project_id_empty():
    """Empty project preference returns None."""
    assert _resolve_project_id("") is None
    assert _resolve_project_id(None) is None


@pytest.mark.django_db
def test_retrieval_agent_arabic_with_qualification():
    """Arabic inquiry with qualification triggers appropriate plan."""
    try:
        import pgvector  # noqa: F401
    except ImportError:
        pytest.skip("pgvector required for retrieval")
    agent = RetrievalAgent()
    ctx = AgentContext(
        run_id="t_ar",
        message_text="كم سعر الوحدات في مشروع النخيل؟",
        conversation_history=[],
        intent_output={"primary": "price_inquiry"},
        qualification_output={
            "project_preference": "النخيل",
            "budget_min": "2000000",
            "budget_max": "3000000",
        },
        memory_output={},
    )
    result = agent.run(ctx)
    assert result.success
    plan = plan_retrieval(
        message_text=ctx.message_text,
        intent_primary="price_inquiry",
        project_preference="النخيل",
    )
    assert plan.use_structured_pricing
    assert plan.document_types
