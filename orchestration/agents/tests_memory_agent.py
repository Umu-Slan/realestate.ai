"""
Tests for Memory Agent and memory schema.
Covers merge rules, explicit vs inferred, persistence, and cross-conversation updates.
"""
import pytest

from orchestration.agents.memory_schema import (
    CustomerMemoryProfile,
    MemoryFact,
    should_overwrite,
    merge_fact_value,
    MEMORY_FIELDS,
)
from orchestration.agents.memory_merger import (
    facts_from_intent_entities,
    facts_from_qualification,
    merge_into_profile,
    detect_rejected_options,
    detect_financing_preference,
)


# --- Memory schema ---
def test_memory_fact_strength_source():
    """MemoryFact validates strength and source."""
    f = MemoryFact(value="معادي", strength="strong", source="explicit")
    assert f.strength == "strong"
    assert f.source == "explicit"
    f2 = MemoryFact(value=1, strength="invalid", source="invalid")
    assert f2.strength == "medium"
    assert f2.source == "inferred"


def test_should_overwrite_strong_beats_weak():
    """Strong fact overwrites weak."""
    strong = MemoryFact(value="x", strength="strong", source="explicit")
    weak = MemoryFact(value="y", strength="weak", source="inferred")
    assert should_overwrite(weak, strong) is True
    assert should_overwrite(strong, weak) is False


def test_should_overwrite_explicit_beats_inferred_same_strength():
    """Explicit beats inferred when strength equal."""
    explicit = MemoryFact(value="x", strength="medium", source="explicit")
    inferred = MemoryFact(value="y", strength="medium", source="inferred")
    assert should_overwrite(inferred, explicit) is True
    assert should_overwrite(explicit, inferred) is False


def test_merge_fact_value_locations_accumulates():
    """preferred_locations accumulates and dedupes."""
    existing = ["المعادي"]
    incoming = ["6 أكتوبر"]
    out = merge_fact_value(existing, incoming, "preferred_locations")
    assert "المعادي" in out
    assert "6 أكتوبر" in out
    out2 = merge_fact_value(existing, "المعادي", "preferred_locations")
    assert out2 == ["المعادي"]


def test_profile_set_fact_respects_strength():
    """Strong overwrites weak; weak does not overwrite strong."""
    p = CustomerMemoryProfile()
    p.set_fact("budget", {"min": 1e6, "max": 1.5e6}, strength="strong", source="explicit")
    assert p.budget
    ok = p.set_fact("budget", {"min": 2e6}, strength="weak", source="inferred")
    assert ok is False
    assert p.budget.get("min") == 1_000_000


def test_profile_set_fact_list_accumulates():
    """preferred_locations and rejected_options accumulate."""
    p = CustomerMemoryProfile()
    p.set_fact("preferred_locations", ["المعادي"], strength="strong", source="explicit")
    p.set_fact("preferred_locations", ["6 أكتوبر"], strength="weak", source="inferred")
    assert "المعادي" in p.preferred_locations
    assert "6 أكتوبر" in p.preferred_locations


def test_profile_to_dict_roundtrip():
    """Profile serializes and deserializes."""
    p = CustomerMemoryProfile()
    p.set_fact("property_type", "apartment", strength="strong", source="explicit")
    p.set_fact("bedrooms", 3, strength="medium", source="explicit")
    d = p.to_dict()
    p2 = CustomerMemoryProfile.from_dict(d)
    assert p2.property_type == "apartment"
    assert p2.bedrooms == 3


# --- Merger ---
def test_facts_from_intent_entities():
    """Intent entities convert to facts."""
    entities = {
        "budget": {"min": 1.8e6, "max": 2.2e6},
        "location": "المعادي",
        "property_type": "villa",
        "bedrooms": 3,
    }
    facts = facts_from_intent_entities(entities, confidence=0.8)
    assert any(f[0] == "budget" for f in facts)
    assert any(f[0] == "preferred_locations" for f in facts)
    assert any(f[0] == "property_type" for f in facts)
    assert any(f[0] == "bedrooms" for f in facts)


def test_facts_from_qualification():
    """Qualification converts to facts."""
    q = {
        "budget_min": "2000000",
        "budget_max": "2500000",
        "location_preference": "6 أكتوبر",
        "property_type": "apartment",
        "purpose": "residence",
        "urgency": "immediate",
    }
    facts = facts_from_qualification(q, confidence="high")
    assert any(f[0] == "budget" for f in facts)
    assert any(f[0] == "preferred_locations" for f in facts)
    assert any(f[0] == "investment_vs_residence" for f in facts)


def test_detect_rejected_options():
    """Rejected options extraction."""
    assert "المعادي" in detect_rejected_options("مش عايز المعادي")
    assert len(detect_rejected_options("لا أكتوبر")) > 0


def test_detect_financing_preference():
    """Financing style detection."""
    assert detect_financing_preference("عايز تقسيط") == "installment"
    assert detect_financing_preference("كاش") == "cash"
    assert detect_financing_preference("hello") is None


def test_merge_into_profile_updates_count():
    """merge_into_profile returns update count."""
    p = CustomerMemoryProfile()
    updated = merge_into_profile(
        p,
        intent_entities={"location": "المعادي", "budget": {"min": 2e6, "max": 2.5e6}},
        qualification={"property_type": "apartment"},
        message_text="عايز شقة",
        intent_confidence=0.8,
        qualification_confidence="high",
    )
    assert updated >= 2
    assert p.preferred_locations
    assert p.budget


# --- Memory Agent integration ---
@pytest.mark.django_db
def test_memory_agent_runs_after_qualification():
    """Memory agent runs and merges intent + qualification."""
    from orchestration.agents import get_agent
    from orchestration.agents.base import AgentContext

    ctx = AgentContext(
        run_id="test",
        message_text="عايز شقة 2 مليون في المعادي",
        conversation_history=[],
        channel="web",
        use_llm=False,
    )
    # Simulate intent and qualification outputs (normally from prior agents)
    ctx.intent_output = {
        "primary": "property_purchase",
        "entities": {
            "budget": {"min": 1.8e6, "max": 2.2e6},
            "location": "المعادي",
            "property_type": "apartment",
        },
        "confidence": 0.8,
    }
    ctx.qualification_output = {
        "budget_min": 2_000_000,
        "budget_max": 2_500_000,
        "location_preference": "المعادي",
        "property_type": "apartment",
        "confidence": "high",
    }

    agent = get_agent("memory")
    result = agent.run(ctx)
    assert result.success
    assert ctx.memory_output
    profile = ctx.memory_output.get("customer_profile") or {}
    assert profile.get("preferred_locations")
    assert profile.get("budget")
    assert profile.get("property_type") == "apartment"


@pytest.mark.django_db
def test_memory_agent_skips_spam():
    """Memory agent skips update for spam."""
    from orchestration.agents import get_agent
    from orchestration.agents.base import AgentContext

    ctx = AgentContext(
        run_id="test",
        message_text="spam link http://x.com",
        conversation_history=[],
    )
    ctx.intent_output = {"is_spam": True, "primary": "spam"}
    agent = get_agent("memory")
    result = agent.run(ctx)
    assert result.success
    assert ctx.memory_output.get("customer_type_hint") == "spam"


def test_memory_across_conversations_accumulates():
    """Simulated: message 1 sets budget, message 2 adds location; both persist in profile."""
    p = CustomerMemoryProfile()
    merge_into_profile(
        p,
        intent_entities={"budget": {"min": 2e6, "max": 2.5e6}},
        qualification={},
        message_text="ميزانيتي 2 مليون",
        intent_confidence=0.85,
    )
    assert p.budget

    merge_into_profile(
        p,
        intent_entities={"location": "6 أكتوبر"},
        qualification={"location_preference": "6 أكتوبر"},
        message_text="عايز في أكتوبر",
        intent_confidence=0.8,
    )
    assert "6 أكتوبر" in p.preferred_locations
    assert p.budget  # Preserved


def test_memory_strong_overwrites_weak_across_turns():
    """Strong fact in turn 2 overwrites weak fact from turn 1."""
    p = CustomerMemoryProfile()
    p.set_fact("property_type", "villa", strength="weak", source="inferred")
    p.set_fact("property_type", "apartment", strength="strong", source="explicit")
    assert p.property_type == "apartment"


def test_memory_weak_does_not_overwrite_strong():
    """Weak fact does not overwrite strong."""
    p = CustomerMemoryProfile()
    p.set_fact("investment_vs_residence", "investment", strength="strong", source="explicit")
    ok = p.set_fact("investment_vs_residence", "residence", strength="weak", source="inferred")
    assert ok is False
    assert p.investment_vs_residence == "investment"
