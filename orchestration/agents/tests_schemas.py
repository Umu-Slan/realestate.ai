"""
Schema validation tests for all agent output schemas.
Ensures contracts are explicit, validated, and reusable.
"""
import pytest
from decimal import Decimal

from orchestration.agents.schemas import (
    IntentAgentOutput,
    MemoryAgentOutput,
    LeadQualificationAgentOutput,
    RetrievalAgentOutput,
    RetrievalSource,
    PropertyMatch,
    PropertyMatchingAgentOutput,
    RecommendationAgentOutput,
    SalesStrategyAgentOutput,
    PersuasionAgentOutput,
    ConversationPlanAgentOutput,
    FollowUpAgentOutput,
    ScoringSummary,
    ResponseComposerAgentOutput,
    SchemaValidationError,
    AGENT_SCHEMAS,
)


# --- Intent Agent ---
def test_intent_agent_output_valid():
    """IntentAgentOutput accepts valid values."""
    o = IntentAgentOutput(
        primary="price_inquiry",
        secondary=["project_inquiry"],
        confidence=0.85,
        is_support=False,
        is_spam=False,
        is_broker=False,
    )
    assert o.primary == "price_inquiry"
    assert o.confidence == 0.85
    d = o.to_dict()
    assert d["primary"] == "price_inquiry"
    assert d["confidence"] == 0.85
    restored = IntentAgentOutput.from_dict(d)
    assert restored.primary == o.primary


def test_intent_agent_output_confidence_clamped():
    """Confidence is clamped to 0-1."""
    o = IntentAgentOutput(primary="other", confidence=1.5)
    assert o.confidence == 1.0
    o2 = IntentAgentOutput(primary="other", confidence=-0.1)
    assert o2.confidence == 0.0


def test_intent_agent_output_unknown_intent_maps_to_other():
    """Unknown primary intent maps to other."""
    o = IntentAgentOutput(primary="nonexistent_intent", confidence=0.5)
    assert o.primary == "other"


# --- Memory Agent ---
def test_memory_agent_output_valid():
    """MemoryAgentOutput round-trips."""
    o = MemoryAgentOutput(
        conversation_summary="5 messages",
        customer_type_hint="new_lead",
        key_facts=["budget 2M"],
        prior_intents=["user_message"],
        message_count=5,
    )
    d = o.to_dict()
    assert d["message_count"] == 5
    restored = MemoryAgentOutput.from_dict(d)
    assert restored.customer_type_hint == "new_lead"


# --- Lead Qualification Agent ---
def test_lead_qualification_output_valid():
    """LeadQualificationAgentOutput with valid data."""
    o = LeadQualificationAgentOutput(
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="New Cairo",
        confidence="high",
        missing_fields=["project"],
    )
    d = o.to_dict()
    assert d["budget_min"] == "2000000"
    assert d["confidence"] == "high"
    restored = LeadQualificationAgentOutput.from_dict(d)
    assert restored.budget_min == Decimal("2000000")


def test_lead_qualification_budget_inversion_raises():
    """budget_min > budget_max raises SchemaValidationError."""
    with pytest.raises(SchemaValidationError) as exc:
        LeadQualificationAgentOutput(
            budget_min=Decimal("3000000"),
            budget_max=Decimal("2000000"),
            confidence="high",
        )
    assert "budget" in str(exc.value).lower()


def test_lead_qualification_invalid_confidence_raises():
    """Invalid confidence level raises."""
    with pytest.raises(SchemaValidationError) as exc:
        LeadQualificationAgentOutput(confidence="invalid_level")
    assert "confidence" in str(exc.value).lower()


# --- Retrieval Agent ---
def test_retrieval_source_roundtrip():
    """RetrievalSource serializes and deserializes."""
    s = RetrievalSource(chunk_id=42, document_title="Project Brochure")
    d = s.to_dict()
    assert d["chunk_id"] == 42
    restored = RetrievalSource.from_dict(d)
    assert restored.chunk_id == 42


def test_retrieval_agent_output_valid():
    """RetrievalAgentOutput with sources."""
    sources = [RetrievalSource(1, "Doc1"), RetrievalSource(2, "Doc2")]
    o = RetrievalAgentOutput(
        query="price in maadi",
        document_types=["project_pdf"],
        retrieval_sources=sources,
        has_verified_pricing=True,
    )
    d = o.to_dict()
    assert len(d["retrieval_sources"]) == 2
    assert d["sources_count"] == 2
    assert d["has_verified_pricing"] is True


# --- Property Match ---
def test_property_match_valid():
    """PropertyMatch with all fields."""
    m = PropertyMatch(
        project_id=1,
        project_name="Sun City",
        location="6 October",
        price_min=1500000.0,
        price_max=2500000.0,
        fit_score=0.9,
        confidence=0.85,
        has_verified_pricing=True,
        match_reasons=["budget_fit", "location_match"],
    )
    d = m.to_dict()
    assert d["project_id"] == 1
    assert d["fit_score"] == 0.9
    assert "budget_fit" in d["match_reasons"]


def test_property_match_fit_score_clamped():
    """fit_score clamped to 0-1."""
    m = PropertyMatch(project_id=1, project_name="X", fit_score=2.0)
    assert m.fit_score == 1.0


# --- Property Matching Agent ---
def test_property_matching_output_valid():
    """PropertyMatchingAgentOutput round-trip."""
    m1 = PropertyMatch(project_id=1, project_name="A", fit_score=0.8)
    o = PropertyMatchingAgentOutput(
        matches=[m1],
        overall_confidence=0.75,
        data_completeness="partial",
        qualification_summary="Budget 2-3M",
        alternatives=[{"project_id": 2, "project_name": "B", "rationale": "Alternative"}],
    )
    d = o.to_dict()
    assert len(d["matches"]) == 1
    assert d["data_completeness"] == "partial"
    restored = PropertyMatchingAgentOutput.from_dict(d)
    assert len(restored.matches) == 1
    assert restored.matches[0].project_id == 1


# --- Recommendation Agent ---
def test_recommendation_output_valid():
    """RecommendationAgentOutput with top_recommendations, why_it_matches, tradeoffs."""
    top = [
        {
            "project_id": 1,
            "project_name": "A",
            "why_it_matches": ["budget_fit", "location_match"],
            "tradeoffs": [],
            "fit_score": 0.9,
        },
    ]
    o = RecommendationAgentOutput(
        matches=top,
        top_recommendations=top,
        alternatives=[{"project_id": 2, "project_name": "B", "rationale": "Alt"}],
        qualification_summary="Budget 2M",
        data_completeness="full",
        overall_confidence=0.88,
        recommendation_confidence=0.88,
        response_text="نوصي بمشروع A",
    )
    d = o.to_dict()
    assert d["overall_confidence"] == 0.88
    assert d["recommendation_confidence"] == 0.88
    assert "top_recommendations" in d
    assert d["top_recommendations"][0]["why_it_matches"] == ["budget_fit", "location_match"]
    assert "نوصي" in d["response_text"]
    restored = RecommendationAgentOutput.from_dict(d)
    assert restored.overall_confidence == 0.88


def test_recommendation_output_confidence_clamped():
    """overall_confidence and recommendation_confidence clamped to 0-1."""
    o = RecommendationAgentOutput(overall_confidence=1.5)
    assert o.overall_confidence == 1.0
    assert o.recommendation_confidence == 1.0


# --- Sales Strategy Agent ---
def test_scoring_summary_valid():
    """ScoringSummary validates score range."""
    s = ScoringSummary(score=75, temperature="warm", confidence="high")
    d = s.to_dict()
    assert d["score"] == 75
    s2 = ScoringSummary(score=150)
    assert s2.score == 100


def test_sales_strategy_output_valid():
    """SalesStrategyAgentOutput with strategy, objective, persuasive_angle, recommended_cta."""
    sc = ScoringSummary(score=70, temperature="warm", confidence="medium")
    o = SalesStrategyAgentOutput(
        approach="qualify",
        objection_key="price_too_high",
        next_best_action="ask_budget: Missing budget",
        tone="empathetic",
        key_points=["budget_known"],
        scoring=sc,
        strategy="qualify",
        objective="Qualify budget to filter options",
        persuasive_angle="Understanding your budget helps us show only options that fit.",
        recommended_cta="ask_budget",
    )
    d = o.to_dict()
    assert d["approach"] == "qualify"
    assert d["scoring"]["score"] == 70
    assert d["recommended_cta"] == "ask_budget"
    assert d["persuasive_angle"]
    restored = SalesStrategyAgentOutput.from_dict(d)
    assert restored.scoring is not None
    assert restored.recommended_cta == "ask_budget"


def test_sales_strategy_output_invalid_approach_defaults():
    """Invalid approach defaults to nurture."""
    o = SalesStrategyAgentOutput(approach="invalid_approach")
    assert o.approach == "nurture"


def test_sales_strategy_output_invalid_cta_defaults():
    """Invalid recommended_cta defaults to nurture."""
    o = SalesStrategyAgentOutput(recommended_cta="invalid_cta")
    assert o.recommended_cta == "nurture"


# --- Response Composer ---
def test_response_composer_output_valid():
    """ResponseComposerAgentOutput round-trip with reply_text, CTA, reasoning."""
    o = ResponseComposerAgentOutput(
        reply_text="مرحباً! كيف يمكنني مساعدتك؟",
        cta="ask_budget",
        reasoning_summary_for_operator="approach=nurture | cta=ask_budget",
        composed_from=["sales_strategy", "retrieval", "sales_engine"],
    )
    d = o.to_dict()
    assert "مرحباً" in d["reply_text"]
    assert d["cta"] == "ask_budget"
    assert "approach" in d["reasoning_summary_for_operator"]
    assert "sales_engine" in d["composed_from"]
    assert d["draft_response"] == d["reply_text"]
    restored = ResponseComposerAgentOutput.from_dict(d)
    assert restored.reply_text == o.reply_text
    assert restored.cta == o.cta


# --- Schema registry ---
def test_agent_schemas_registry_complete():
    """All agents have schemas in registry."""
    expected = [
        "intent", "memory", "lead_qualification", "retrieval",
        "property_matching", "recommendation", "sales_strategy",
        "persuasion", "conversation_plan", "response_composer",
        "follow_up",
    ]
    for name in expected:
        assert name in AGENT_SCHEMAS
        assert AGENT_SCHEMAS[name] is not None


# --- Persistence / JSON suitability ---
def test_all_schemas_to_dict_json_serializable():
    """All schema to_dict() outputs are JSON-serializable (no Decimal, etc in leaf values)."""
    import json

    schemas_to_test = [
        IntentAgentOutput(primary="other").to_dict(),
        MemoryAgentOutput().to_dict(),
        LeadQualificationAgentOutput().to_dict(),
        RetrievalAgentOutput().to_dict(),
        PropertyMatchingAgentOutput().to_dict(),
        RecommendationAgentOutput().to_dict(),
        SalesStrategyAgentOutput().to_dict(),
        PersuasionAgentOutput().to_dict(),
        ConversationPlanAgentOutput().to_dict(),
        FollowUpAgentOutput().to_dict(),
        ResponseComposerAgentOutput().to_dict(),
    ]
    for d in schemas_to_test:
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)
        loaded = json.loads(json_str)
        assert isinstance(loaded, dict)
