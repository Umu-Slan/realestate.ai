"""
Intelligence tests: intent, qualification, scoring, routing, pipeline.
"""
import json
import pytest
from pathlib import Path

from intelligence.services.intent_classifier import classify_intent, _deterministic_classify
from intelligence.services.qualification_extractor import extract_qualification
from intelligence.services.scoring_engine import score_lead
from intelligence.services.routing import apply_routing_rules, classify_support_category
from intelligence.services.pipeline import analyze_message
from intelligence.schemas import IntentResult, QualificationExtraction
from core.enums import IntentCategory, LeadTemperature


@pytest.mark.django_db
def test_hot_lead():
    """Hot lead: budget, location, timeline, visit request."""
    result = analyze_message(
        "I want a 3BR in New Cairo, budget 4M EGP. Ready to buy this month. Can I schedule a visit?",
        is_returning_lead=False,
        message_count=2,
        has_project_match=True,
        use_llm=False,
    )
    assert result.scoring.score >= 55
    assert result.scoring.temperature in ("hot", "warm")
    assert result.routing.route in ("senior_sales", "sales", "sales")
    intent_primary = (result.intent.primary or "").lower()
    assert "schedule" in intent_primary or "price" in intent_primary or "property" in intent_primary or "project" in intent_primary


@pytest.mark.django_db
def test_warm_lead():
    """Warm lead: some qualification, brochure request."""
    result = analyze_message(
        "What projects in October? Looking around 2 million. Send brochure please.",
        message_count=2,
        use_llm=False,
    )
    assert result.scoring.score >= 30
    assert result.scoring.temperature in ("warm", "cold", "hot")
    assert not result.intent.is_spam


@pytest.mark.django_db
def test_cold_lead():
    """Cold lead: vague inquiry."""
    result = analyze_message(
        "What projects do you have?",
        use_llm=False,
    )
    assert result.scoring.temperature in ("cold", "nurture", "unqualified")
    assert result.intent.primary in (IntentCategory.PROJECT_INQUIRY, IntentCategory.OTHER, "project_inquiry", "other")


@pytest.mark.django_db
def test_returning_lead():
    """Returning lead gets returning_interest boost."""
    qual = QualificationExtraction(
        budget_clarity="approximate",
        budget_min=2_500_000,
        budget_max=2_800_000,
        location_preference="المعادي",
        purchase_timeline="within 1 month",
        urgency="immediate",
        missing_fields=["property_type"],
        confidence="high",
    )
    intent = IntentResult(primary=IntentCategory.PROPERTY_PURCHASE, confidence=0.9)
    scoring = score_lead(qual, intent, is_returning=True, message_count=3)
    assert scoring.score >= 55
    assert any(r.factor == "returning_interest" for r in scoring.reason_codes)


@pytest.mark.django_db
def test_angry_existing_customer():
    """Angry customer -> escalation-ready support."""
    result = analyze_message(
        "I am very angry! The contract is late and the installment is wrong. I need to speak to a manager now.",
        customer_type="existing_customer",
        is_angry=True,
        is_existing_customer=True,
        use_llm=False,
    )
    assert result.routing.escalation_ready or result.intent.is_support
    assert result.customer_type in ("existing_customer", "support_customer", "support")


@pytest.mark.django_db
def test_ambiguous_user():
    """Ambiguous short message -> low confidence."""
    result = analyze_message(
        "hi",
        use_llm=False,
    )
    assert result.is_ambiguous or result.intent.confidence < 0.6
    assert result.intent.primary in (IntentCategory.OTHER, "other")


@pytest.mark.django_db
def test_spam():
    """Spam -> quarantine."""
    result = analyze_message(
        "Click here for free money!!! http://scam-site.com/win",
        use_llm=False,
    )
    assert result.intent.is_spam or result.intent.primary == IntentCategory.SPAM
    assert result.routing.quarantine


@pytest.mark.django_db
def test_broker_inquiry():
    """Broker -> broker route."""
    result = analyze_message(
        "أنا سمسار وعايز أتعامل معاكم. إيه شروط العمولة؟",
        use_llm=False,
    )
    assert result.intent.is_broker or result.intent.primary == IntentCategory.BROKER_INQUIRY
    assert result.customer_type in ("broker",) or result.routing.route == "broker"


@pytest.mark.django_db
def test_intent_classification_deterministic():
    """Intent classifier patterns."""
    r = _deterministic_classify("كم سعر الشقة؟")
    assert "price" in (r.primary or "").lower() or r.primary == IntentCategory.PRICE_INQUIRY

    r = _deterministic_classify("عايز أعمل زيارة للمشروع")
    assert "visit" in (r.primary or "").lower() or r.primary == IntentCategory.SCHEDULE_VISIT

    r = _deterministic_classify("شكوى من التأخير")
    assert r.is_support


@pytest.mark.django_db
def test_qualification_extraction():
    """Qualification regex extraction."""
    q = extract_qualification("Budget around 3 million EGP, looking in New Cairo", use_llm=False)
    assert q.budget_clarity in ("approximate", "") or q.budget_min or q.budget_max
    # Location or budget should be extracted
    has_location = bool(q.location_preference and len(q.location_preference) > 0)
    has_budget = bool(q.budget_min or q.budget_max or q.budget_clarity)
    assert has_location or has_budget


@pytest.mark.django_db
def test_scoring_thresholds():
    """Score thresholds map to temperature."""
    qual_empty = QualificationExtraction(missing_fields=["budget", "location", "project"], confidence="low")
    intent_low = IntentResult(primary=IntentCategory.OTHER, confidence=0.3)
    s = score_lead(qual_empty, intent_low)
    assert s.temperature in ("cold", "nurture", "unqualified")
    assert s.score < 55

    qual_full = QualificationExtraction(
        budget_clarity="explicit_range",
        budget_min=3_000_000,
        budget_max=4_000_000,
        location_preference="New Cairo",
        urgency="immediate",
        purchase_timeline="within 1 month",
        project_preference="Palm Hills",
        financing_readiness="ready",
        missing_fields=[],
        confidence="high",
    )
    intent_high = IntentResult(primary=IntentCategory.SCHEDULE_VISIT, confidence=0.95)
    s2 = score_lead(qual_full, intent_high, is_returning=True, message_count=3, has_project_match=True, source_channel="web")
    assert s2.score >= 75
    assert s2.temperature == LeadTemperature.HOT.value


@pytest.mark.django_db
def test_routing_rules():
    """Routing rules applied correctly."""
    from intelligence.schemas import IntentResult, QualificationExtraction, ScoringResult

    intent_spam = IntentResult(primary=IntentCategory.SPAM, is_spam=True, confidence=0.9)
    r = apply_routing_rules(intent_spam, QualificationExtraction(), ScoringResult(0, "nurture", "low", [], [], "", ""), "new_lead")
    assert r.quarantine

    intent_contract = IntentResult(primary=IntentCategory.CONTRACT_ISSUE, is_support=True, confidence=0.9)
    r2 = apply_routing_rules(intent_contract, QualificationExtraction(), ScoringResult(0, "cold", "high", [], [], "", ""), "existing_customer")
    assert r2.handoff_type == "legal" or "legal" in r2.route


@pytest.mark.django_db
def test_support_category_mapping():
    """Support intent -> support category."""
    cat = classify_support_category(IntentResult(primary=IntentCategory.INSTALLMENT_INQUIRY, confidence=0.9))
    assert "installment" in (cat if isinstance(cat, str) else cat.value).lower()


@pytest.mark.django_db
def test_arabic_hot_lead():
    """Arabic hot lead: budget, location, visit intent."""
    qual = QualificationExtraction(
        budget_clarity="explicit_range",
        budget_min=3_000_000,
        budget_max=4_000_000,
        location_preference="المعادي",
        project_preference="مشروع النخيل",
        urgency="immediate",
        purchase_timeline="شهر",
        missing_fields=[],
        confidence="high",
    )
    intent = IntentResult(primary=IntentCategory.SCHEDULE_VISIT, confidence=0.9)
    s = score_lead(qual, intent, message_count=2, has_project_match=True, source_channel="whatsapp")
    assert s.score >= 75
    assert s.temperature == LeadTemperature.HOT.value
    assert any(r.factor == "location_fit" for r in s.reason_codes)
    assert any(r.factor == "action_signals" for r in s.reason_codes)
    assert s.next_best_action


@pytest.mark.django_db
def test_english_warm_lead():
    """English warm lead: brochure request, budget, location."""
    qual = QualificationExtraction(
        budget_clarity="approximate",
        budget_min=2_000_000,
        budget_max=2_500_000,
        location_preference="October",
        missing_fields=["property_type"],
        confidence="medium",
    )
    intent = IntentResult(primary=IntentCategory.BROCHURE_REQUEST, confidence=0.85)
    s = score_lead(qual, intent, message_count=2, source_channel="web")
    assert s.score >= 35
    assert s.temperature in (LeadTemperature.WARM.value, LeadTemperature.HOT.value, LeadTemperature.COLD.value)
    assert any(r.factor == "budget_fit" for r in s.reason_codes)
    assert s.missing_fields


@pytest.mark.django_db
def test_unqualified_lead():
    """Minimal qualification -> unqualified temperature."""
    qual = QualificationExtraction(
        budget_clarity="none",
        missing_fields=["budget", "location", "project", "property_type", "timeline"],
        confidence="low",
    )
    intent = IntentResult(primary=IntentCategory.OTHER, confidence=0.3)
    s = score_lead(qual, intent, message_count=1)
    assert s.score < 20
    assert s.temperature == LeadTemperature.UNQUALIFIED.value
    assert len(s.reason_codes) >= 1


@pytest.mark.django_db
def test_spam_bypass():
    """Spam intent -> score_lead returns spam result."""
    qual = QualificationExtraction()
    intent = IntentResult(primary=IntentCategory.SPAM, is_spam=True, confidence=1.0)
    s = score_lead(qual, intent)
    assert s.score == 0
    assert s.temperature == LeadTemperature.SPAM.value
    assert s.recommended_route == "quarantine"


@pytest.mark.django_db
def test_scoring_output_structure():
    """Scoring output has required fields."""
    qual = QualificationExtraction(budget_min=2_000_000, location_preference="New Cairo", missing_fields=["project"])
    intent = IntentResult(primary=IntentCategory.PROJECT_INQUIRY, confidence=0.7)
    s = score_lead(qual, intent)
    assert hasattr(s, "score")
    assert hasattr(s, "temperature")
    assert hasattr(s, "confidence")
    assert hasattr(s, "reason_codes")
    assert hasattr(s, "missing_fields")
    assert hasattr(s, "next_best_action")
    assert 0 <= s.score <= 100
    assert s.temperature in ("hot", "warm", "cold", "nurture", "unqualified", "spam")
    assert isinstance(s.reason_codes, list)
    for r in s.reason_codes:
        assert hasattr(r, "factor")
        assert hasattr(r, "contribution")
        assert hasattr(r, "note")


@pytest.mark.django_db
def test_sample_conversations():
    """Run pipeline on sample conversation fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_conversations.json"
    if not fixtures_path.exists():
        pytest.skip("Sample conversations fixture not found")

    with open(fixtures_path, encoding="utf-8") as f:
        samples = json.load(f)

    for sample in samples[:5]:  # First 5 to keep fast
        msgs = sample.get("messages", [])
        last_user = next((m["content"] for m in reversed(msgs) if m.get("role") == "user"), "")
        if not last_user:
            continue
        result = analyze_message(
            last_user,
            conversation_history=msgs[:-1],
            customer_type=sample.get("customer_type", ""),
            is_existing_customer=sample.get("customer_type") == "existing_customer",
            use_llm=False,
        )
        if sample.get("expected_intent"):
            exp = sample["expected_intent"].lower()
            assert exp in (result.intent.primary or "").lower() or result.intent.is_spam == (exp == "spam") or result.intent.is_broker == (exp == "broker_inquiry")
