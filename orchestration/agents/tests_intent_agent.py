"""
Tests for Intent Agent and intent detector.
Realistic Arabic and English examples for Egyptian real estate.
"""
import pytest

from orchestration.agents.intent_detector import (
    detect_intent,
    IntentDetectionResult,
    SALES_INTENTS,
    ENTITY_KEYS,
)


def test_intent_detector_property_search_ar():
    """Property search intent in Arabic."""
    r = detect_intent("عايز شقة في المعادي", use_llm=False)
    assert r.intent == "property_search"
    assert r.confidence >= 0.5
    assert r.legacy_primary == "property_purchase"
    assert r.extracted_entities.get("location") == "معادي"


def test_intent_detector_property_search_en():
    """Property search intent in English."""
    r = detect_intent("Looking for apartment in New Cairo", use_llm=False)
    assert r.intent == "property_search"
    assert r.legacy_primary == "property_purchase"
    assert r.extracted_entities.get("location") == "القاهرة الجديدة"


def test_intent_detector_price_inquiry_ar():
    """Price inquiry in Arabic."""
    r = detect_intent("كام السعر؟", use_llm=False)
    assert r.intent == "price_inquiry"
    assert r.legacy_primary == "price_inquiry"
    assert r.confidence >= 0.5


def test_intent_detector_price_inquiry_with_budget():
    """Property search with budget and location extraction."""
    r = detect_intent("أريد شقة 2 مليون في أكتوبر", use_llm=False)
    assert r.intent == "property_search"
    assert r.extracted_entities.get("budget")
    assert r.extracted_entities.get("location") == "6 أكتوبر"


def test_intent_detector_location_inquiry_ar():
    """Location inquiry in Arabic."""
    r = detect_intent("فيين المشروع؟", use_llm=False)
    assert r.intent == "location_inquiry"
    assert r.legacy_primary == "location_inquiry"


def test_intent_detector_project_details():
    """Project details request."""
    r = detect_intent("تفاصيل المشروع", use_llm=False)
    assert r.intent == "project_details"
    assert r.legacy_primary == "project_inquiry"


def test_intent_detector_investment_inquiry():
    """Investment intent."""
    r = detect_intent("عايز استثمار في العقارات", use_llm=False)
    assert r.intent == "investment_inquiry"
    assert r.legacy_primary == "investment_inquiry"


def test_intent_detector_visit_request():
    """Visit / site tour request."""
    r = detect_intent("أريد معاينة المشروع", use_llm=False)
    assert r.intent == "visit_request"
    assert r.legacy_primary == "schedule_visit"


def test_intent_detector_booking_intent():
    """Booking / reservation intent."""
    r = detect_intent("احجز وحدة لي", use_llm=False)
    assert r.intent == "booking_intent"
    assert r.legacy_primary == "schedule_visit"


def test_intent_detector_support_request():
    """Support / complaint intent."""
    r = detect_intent("عندي شكوى في التسليم", use_llm=False)
    assert r.intent == "support_request"
    assert r.is_support is True


def test_intent_detector_negotiation():
    """Negotiation / discount intent."""
    r = detect_intent("السعر غالي، ممكن خصم؟", use_llm=False)
    assert r.intent == "negotiation"
    assert r.legacy_primary == "price_inquiry"


def test_intent_detector_unclear_vague():
    """Vague / short messages."""
    r = detect_intent("مرحبا", use_llm=False)
    assert r.intent == "unclear"
    assert r.confidence < 0.6


def test_intent_detector_unclear_empty():
    """Very short or empty."""
    r = detect_intent("ه", use_llm=False)
    assert r.intent == "unclear"
    assert r.confidence <= 0.4


def test_intent_detector_entity_budget_million():
    """Budget extraction: million."""
    r = detect_intent("ميزانيتي 2.5 مليون", use_llm=False)
    assert r.extracted_entities.get("budget")
    budget = r.extracted_entities["budget"]
    assert "min" in budget or "max" in budget or "value" in budget


def test_intent_detector_entity_bedrooms():
    """Bedroom count extraction."""
    r = detect_intent("أريد شقة 3 غرف في المعادي", use_llm=False)
    assert r.extracted_entities.get("bedrooms") == 3


def test_intent_detector_entity_property_type():
    """Property type extraction."""
    r = detect_intent("Looking for villa in Sheikh Zayed", use_llm=False)
    assert r.extracted_entities.get("property_type") == "villa"


def test_intent_detector_stage_hint_visit():
    """Stage hint for visit request."""
    r = detect_intent("أريد زيارة الموقع", use_llm=False)
    assert r.stage_hint == "visit_planning"


def test_intent_detector_stage_hint_booking():
    """Stage hint for booking."""
    r = detect_intent("احجز لي وحدة", use_llm=False)
    assert r.stage_hint == "booking"


def test_intent_detector_spam_url():
    """Spam detection: URL."""
    r = detect_intent("شوف العرض http://spam.com", use_llm=False)
    assert r.is_spam is True


def test_intent_detector_broker():
    """Broker inquiry."""
    r = detect_intent("أنا سمسار وأريد التعاون", use_llm=False)
    assert r.is_broker is True


def test_intent_detector_sales_intents_known():
    """All detected intents are in taxonomy."""
    examples = [
        "عايز شقة",
        "كام السعر",
        "فيين المشروع",
        "تفاصيل",
        "استثمار",
        "أريد زيارة",
        "احجز",
        "شكوى",
        "خصم",
        "مرحبا",
    ]
    for msg in examples:
        r = detect_intent(msg, use_llm=False)
        assert r.intent in SALES_INTENTS


def test_intent_detector_entity_keys_valid():
    """Extracted entities use known keys only."""
    r = detect_intent("شقة 2 مليون في المعادي 3 غرف", use_llm=False)
    for k in r.extracted_entities:
        assert k in ENTITY_KEYS


def test_intent_detector_conversation_history_ignored_without_llm():
    """Deterministic path ignores history (no LLM)."""
    r = detect_intent("كام؟", conversation_history=[{"role": "user", "content": "عايز شقة"}], use_llm=False)
    assert r.intent in ("price_inquiry", "unclear")


@pytest.mark.django_db
def test_intent_agent_integration():
    """Intent Agent produces valid output via pipeline."""
    from orchestration.agents import get_agent
    from orchestration.agents.base import AgentContext

    agent = get_agent("intent")
    ctx = AgentContext(
        run_id="test",
        message_text="عايز شقة 2 مليون في أكتوبر",
        conversation_history=[],
        channel="web",
        use_llm=False,
    )
    result = agent.run(ctx)
    assert result.success
    assert ctx.intent_output
    assert ctx.intent_output.get("primary") == "property_purchase"
    assert ctx.intent_output.get("sales_intent") == "property_search"
    assert "entities" in ctx.intent_output
    assert "stage_hint" in ctx.intent_output
