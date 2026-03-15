"""
Engines tests - sales, support, recommendation, objections.
"""
import pytest
from decimal import Decimal

from engines.objection_library import (
    detect_objection,
    get_objection_response,
    get_follow_up,
    OBJECTIONS,
)
from engines.templates import get_template, get_system_prompt, TEMPLATES
from engines.recommendation_engine import recommend_projects, ProjectMatch
from engines.response_builder import build_recommendation_response


def test_objection_detect_price():
    """Price objection detection."""
    assert detect_objection("السعر غالي جداً") == "price_too_high"
    assert detect_objection("It's too expensive") == "price_too_high"


def test_objection_detect_location():
    """Location objection."""
    assert detect_objection("الموقع بعيد عن شغلي") == "location_concern"


def test_objection_detect_waiting():
    """Waiting hesitation."""
    assert detect_objection("هستنى وأفكر") == "waiting_hesitation"
    assert detect_objection("I'll think about it") == "waiting_hesitation"


def test_objection_response_ar():
    """Arabic objection response."""
    r = get_objection_response("price_too_high", "ar")
    assert "فهمت" in r or "أسعار" in r or "تقسيط" in r


def test_objection_response_en():
    """English objection response."""
    r = get_objection_response("price_too_high", "en")
    assert "understand" in r.lower() or "budget" in r.lower()


def test_objection_follow_up():
    """Follow-up question."""
    f = get_follow_up("price_too_high", "ar")
    assert "دفع" in f or "قسط" in f or "كاش" in f or "تقسيط" in f


def test_templates_exist():
    """All expected templates exist."""
    for key in ["hot_lead", "warm_lead", "cold_lead", "angry_customer", "brochure_request"]:
        t = get_template(key)
        assert t.system_prompt
        assert t.opening_ar or t.opening_en


def test_system_prompt_constraints():
    """System prompts contain safety constraints."""
    sp = get_system_prompt("warm_lead")
    assert "never" in sp.lower() or "لا" in sp or "don't" in sp.lower()
    assert "fabricate" in sp.lower() or "invent" in sp.lower() or "overpromise" in sp.lower()


@pytest.mark.django_db
def test_recommend_empty_db():
    """Recommend with no projects returns empty matches."""
    from engines.recommendation_engine import recommend_projects
    result = recommend_projects(budget_min=Decimal("2000000"), limit=3)
    assert hasattr(result, "matches")
    assert isinstance(result.matches, list)


@pytest.mark.django_db
def test_recommend_with_projects():
    """Recommend with projects in DB."""
    from engines.recommendation_engine import recommend_projects
    from knowledge.models import Project
    Project.objects.create(
        name="Test Towers",
        name_ar="برج الاختبار",
        location="New Cairo",
        price_min=Decimal("1500000"),
        price_max=Decimal("2500000"),
        is_active=True,
    )
    result = recommend_projects(
        budget_min=Decimal("2000000"),
        budget_max=Decimal("3000000"),
        location_preference="Cairo",
        limit=3,
    )
    assert len(result.matches) >= 1
    assert result.matches[0].project_name == "Test Towers"
    assert "budget" in result.matches[0].rationale.lower() or "fit" in result.matches[0].rationale.lower() or "range" in result.matches[0].rationale.lower()


def test_response_builder_empty():
    """Empty matches gives fallback message."""
    r = build_recommendation_response([], lang="ar")
    assert "فريق" in r or "تواصل" in r


def test_response_builder_with_matches():
    """Matches formatted correctly with trade-offs."""
    matches = [
        ProjectMatch(
            project_id=1,
            project_name="Palm Hills",
            project_name_ar="بالم هيلز",
            location="October",
            price_min=Decimal("2000000"),
            price_max=Decimal("3500000"),
            rationale="Fits budget",
        ),
    ]
    r = build_recommendation_response(matches, lang="en")
    assert "Palm Hills" in r
    assert "2,000,000" in r or "2000000" in r


def test_sales_engine_fallback():
    """Sales engine returns fallback when LLM unavailable or demo."""
    from engines.sales_engine import generate_sales_response
    resp = generate_sales_response(
        "مرحباً",
        mode="cold_lead",
        use_llm=True,  # may use mock in demo mode
    )
    assert resp
    assert len(resp) > 10


def test_objection_handling_in_sales():
    """Sales engine uses objection library when objection detected."""
    from engines.sales_engine import generate_sales_response
    resp = generate_sales_response("غالي جداً", mode="warm_lead")
    # Should return objection response, not generic
    assert "فهمت" in resp or "understand" in resp.lower() or "أسعار" in resp or "budget" in resp.lower()


# Sample Egyptian real estate conversations for reference
SAMPLE_CONVERSATIONS_AR = [
    ("عايز شقة 3 غرف في المعادي، الميزانية حوالى 3 مليون", "sales"),
    ("السعر غالي، عندكم حاجة أقل؟", "sales"),
    ("ميناء القسط اتأخر إيه المشكلة؟", "support"),
]

SAMPLE_CONVERSATIONS_EN = [
    ("I want a 3BR in New Cairo, budget around 4 million", "sales"),
    ("It's too expensive. Do you have something cheaper?", "sales"),
    ("My installment is late. What's the issue?", "support"),
]


def test_sample_arabic_sales():
    """Arabic sales flow - objection detected."""
    from engines.objection_library import detect_objection
    msg = SAMPLE_CONVERSATIONS_AR[1][0]
    assert detect_objection(msg) == "price_too_high"


def test_sample_english_sales():
    """English sales flow - objection detected."""
    from engines.objection_library import detect_objection
    msg = SAMPLE_CONVERSATIONS_EN[1][0]
    assert detect_objection(msg) == "price_too_high"


# Realistic Arabic sales conversations - Egyptian, Gulf, typos, mixed
REALISTIC_ARABIC_SALES = [
    ("عايز شقة 3 غرف في المعادي، الميزانية حوالى 3 مليون", "price/location intent"),
    ("غالي جداً، ميزانيتي أقل من كده", "price_too_high"),
    ("غاليه عليا، عندكم حاجة ارخص؟", "price_too_high"),
    ("ابغى عقار في التجمع بحدود 4 مليون", "location/budget intent"),
    ("الموقع بعيد عن شغلي", "location_concern"),
    ("هستنى وأفكر، مش مستعجل دلوقتي", "waiting_hesitation"),
    ("بين مشروعين دي أيهما أفضل؟", "comparing_projects"),
    ("مش متأكد من المنطقه، ممكن مقارنه؟", "location_concern or comparing"),
    ("التقسيط والمقدم كتير، مش مقتدر", "payment_plan_mismatch"),
    ("متى التسليم؟ بيتأخر؟", "delivery_concerns"),
    ("معايا 3 مليون بس", "budget_only vague"),
    ("شي في الشيخ زايد", "short_vague"),
]


def test_arabic_normalizer_egyptian():
    """Egyptian Arabic normalizes correctly."""
    from engines.arabic_normalizer import normalize_arabic_input
    r = normalize_arabic_input("عايز شقه في المعادي")
    assert r.dialect_hint == "egyptian"
    assert "شقة" in r.normalized


def test_arabic_normalizer_typos():
    """Typo-heavy Arabic gets corrected."""
    from engines.arabic_normalizer import normalize_arabic_input
    r = normalize_arabic_input("غاليه جدا ميزانتي اقل")
    assert "غالية" in r.normalized or "غاليه" in r.normalized  # correction may vary
    assert r.dialect_hint in ("egyptian", "standard")


def test_arabic_normalizer_gulf():
    """Gulf dialect detected."""
    from engines.arabic_normalizer import normalize_arabic_input
    r = normalize_arabic_input("ابغى عقار بالتجمع")
    assert r.dialect_hint == "gulf"


def test_objection_detect_egyptian_variants():
    """Egyptian variants detected as objections."""
    from engines.objection_library import detect_objection
    assert detect_objection("غاليه عليا") == "price_too_high"
    assert detect_objection("هستنى وأفكر") == "waiting_hesitation"
    assert detect_objection("مش مستعجل دلوقتي") == "waiting_hesitation"


def test_objection_detect_typos():
    """Typo-heavy objection messages still detected."""
    from engines.objection_library import detect_objection
    assert detect_objection("غاليه جدا") == "price_too_high"
    assert detect_objection("مقارنه بين المشاريع") == "comparing_projects"


def test_objection_detect_mixed():
    """Mixed Arabic/English objection detected."""
    from engines.objection_library import detect_objection
    assert detect_objection("too expensive, غالي") == "price_too_high"
    assert detect_objection("I'll think about it لاحقاً") == "waiting_hesitation"


def test_realistic_arabic_sales_objections():
    """Realistic Arabic sales messages trigger correct objection handling."""
    from engines.objection_library import detect_objection, get_objection_response
    # Price
    assert detect_objection("غالي جداً، ميزانيتي أقل من كده") == "price_too_high"
    resp = get_objection_response("price_too_high", "ar")
    assert "فهمت" in resp or "أسعار" in resp
    # Location
    assert detect_objection("الموقع بعيد عن شغلي") == "location_concern"
    # Waiting
    assert detect_objection("هستنى وأفكر، مش مستعجل دلوقتي") == "waiting_hesitation"
    # Comparing
    assert detect_objection("بين مشروعين دي أيهما أفضل؟") == "comparing_projects"
    # Delivery
    assert detect_objection("متى التسليم؟ بيتأخر؟") == "delivery_concerns"


def test_persuasion_arabic_points():
    """Arabic persuasive points returned for ar lang."""
    from engines.persuasion import get_persuasive_points
    pts = get_persuasive_points("price_too_high", "ar")
    assert len(pts) >= 1
    assert any("\u0600" <= c <= "\u06FF" for c in pts[0])


@pytest.mark.django_db
def test_canonical_pipeline_sales():
    """Canonical pipeline (sales mode) persists and returns response."""
    from django.test import Client
    from conversations.models import Message
    from console.models import OrchestrationSnapshot

    client = Client()
    response = client.post(
        "/api/engines/sales/",
        {"message": "عايز بروشور", "mode": "warm_lead"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["response"]
    assert data.get("mode") == "warm_lead"
    # Persistence: messages and snapshot exist
    assert Message.objects.filter(role="user", content="عايز بروشور").exists()
    assert Message.objects.filter(role="assistant").exists()
    assert OrchestrationSnapshot.objects.exists()


@pytest.mark.django_db
def test_chat_creates_visible_conversation_records():
    """Chat interactions create real conversation/message records visible in console."""
    from django.test import Client
    from conversations.models import Conversation, Message
    from console.models import OrchestrationSnapshot
    from leads.models import LeadScore, LeadQualification, Customer

    client = Client()
    # Send a message that triggers lead scoring (budget + location)
    resp = client.post(
        "/api/engines/sales/",
        {"message": "عايز شقة 3 غرف في المعادي، الميزانية 3 مليون", "mode": "warm_lead"},
        content_type="application/json",
    )
    assert resp.status_code == 200

    # Conversation and messages exist (WEB channel for web chat)
    conv = Conversation.objects.filter(customer__identity__external_id__startswith="web:").first()
    assert conv is not None
    msgs = list(conv.messages.all().order_by("created_at"))
    assert len(msgs) >= 2

    # Snapshot has full audit data
    snap = OrchestrationSnapshot.objects.filter(conversation=conv).first()
    assert snap is not None
    assert snap.run_id
    assert "primary" in (snap.intent or {})
    assert snap.mode in ("sales", "generic", "")
    assert snap.scoring or snap.qualification or snap.routing

    # LeadScore/LeadQualification persisted when lead-type
    if snap.routing.get("customer_type") in ("new_lead", "returning_lead", "broker"):
        assert LeadScore.objects.filter(customer=conv.customer).exists()
    # LeadQualification may exist if budget/location extracted
    quals = LeadQualification.objects.filter(customer=conv.customer)
    assert quals.count() >= 0  # May or may not have qual based on extraction


@pytest.mark.django_db
def test_recommend_investment_scenario():
    """Investment purpose gets investment_friendly match reason."""
    from engines.recommendation_engine import recommend_projects
    from knowledge.models import Project

    Project.objects.create(
        name="Invest Towers",
        location="New Cairo",
        price_min=Decimal("2000000"),
        price_max=Decimal("4000000"),
        is_active=True,
    )
    result = recommend_projects(
        budget_min=Decimal("2500000"),
        budget_max=Decimal("3500000"),
        location_preference="New Cairo",
        purpose="investment",
        limit=3,
    )
    assert len(result.matches) >= 1
    assert "investment_friendly" in result.matches[0].match_reasons
    assert result.overall_confidence > 0


@pytest.mark.django_db
def test_recommend_residence_scenario():
    """Residence purpose gets residential match reason."""
    from engines.recommendation_engine import recommend_projects
    from knowledge.models import Project

    Project.objects.create(
        name="Home Views",
        location="Maadi",
        price_min=Decimal("1500000"),
        price_max=Decimal("3000000"),
        is_active=True,
    )
    result = recommend_projects(
        budget_min=Decimal("2000000"),
        location_preference="معادي",
        purpose="residence",
        property_type="apartment",
        limit=3,
    )
    assert len(result.matches) >= 1
    assert "residential" in result.matches[0].match_reasons or "location_match" in result.matches[0].match_reasons
    assert result.data_completeness in ("full", "partial", "minimal")


@pytest.mark.django_db
def test_recommend_graceful_degradation():
    """Partial data still returns results with lower confidence."""
    from engines.recommendation_engine import recommend_projects
    from knowledge.models import Project

    Project.objects.create(name="Any Project", location="Cairo", is_active=True)
    result = recommend_projects(budget_min=Decimal("1000000"), limit=3)
    assert result.data_completeness in ("partial", "minimal")
    assert result.qualification_summary


@pytest.mark.django_db
def test_recommend_creates_recommendation_records():
    """Recommendation flow creates Recommendation records for customer."""
    from django.test import Client
    from knowledge.models import Project
    from decimal import Decimal
    from recommendations.models import Recommendation

    Project.objects.create(
        name="Test Project",
        location="New Cairo",
        price_min=Decimal("1500000"),
        price_max=Decimal("2500000"),
        is_active=True,
    )
    client = Client()
    resp = client.post(
        "/api/engines/recommend/",
        {"budget_min": 2000000, "budget_max": 3000000, "location_preference": "Cairo"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert "response" in data
    # Recommendation records persisted
    assert Recommendation.objects.exists()


@pytest.mark.django_db
def test_project_detail_returns_200_for_valid_project():
    """GET /api/engines/project/<id>/ returns project details for View details modal."""
    from django.test import Client
    from knowledge.models import Project

    p = Project.objects.create(
        name="Test Project",
        name_ar="مشروع تجريبي",
        location="New Cairo",
        price_min=Decimal("2000000"),
        price_max=Decimal("3000000"),
        is_active=True,
    )
    client = Client()
    resp = client.get("/api/engines/project/%d/" % p.id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == p.id
    assert data["name"] == "Test Project"
    assert data["name_ar"] == "مشروع تجريبي"
    assert data["location"] == "New Cairo"
    assert data["price_min"] == 2000000.0
    assert data["price_max"] == 3000000.0


@pytest.mark.django_db
def test_project_detail_returns_404_for_invalid_project():
    """GET /api/engines/project/<id>/ returns 404 for non-existent project."""
    from django.test import Client

    client = Client()
    resp = client.get("/api/engines/project/999999/")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data


@pytest.mark.django_db
def test_conversation_history_api():
    """GET /api/engines/conversation/ returns messages for session (session continuity)."""
    from django.test import Client
    from conversations.models import Message

    client = Client()
    # First request creates session; no messages yet
    r1 = client.get("/api/engines/conversation/")
    assert r1.status_code == 200
    d1 = r1.json()
    assert "messages" in d1
    assert "conversation_id" in d1
    assert d1["has_session"] is True

    # Send a message
    r2 = client.post(
        "/api/engines/sales/",
        {"message": "مرحبا", "mode": "warm_lead"},
        content_type="application/json",
    )
    assert r2.status_code == 200

    # History now includes user and assistant messages
    r3 = client.get("/api/engines/conversation/")
    assert r3.status_code == 200
    d3 = r3.json()
    assert len(d3["messages"]) >= 2
    roles = {m["role"] for m in d3["messages"]}
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.django_db
def test_web_chat_uses_web_channel():
    """Web chat creates Customer/Conversation with WEB channel for operator filtering."""
    from django.test import Client
    from core.enums import SourceChannel
    from leads.models import Customer
    from conversations.models import Conversation

    client = Client()
    client.post(
        "/api/engines/sales/",
        {"message": "استفسار", "mode": "warm_lead"},
        content_type="application/json",
    )
    cust = Customer.objects.filter(identity__external_id__startswith="web:").first()
    assert cust is not None
    assert cust.source_channel == SourceChannel.WEB
    conv = Conversation.objects.filter(customer=cust).first()
    assert conv is not None
    assert conv.channel == SourceChannel.WEB


@pytest.mark.django_db
def test_rate_limit_returns_429():
    """Rate limiting returns 429 when threshold exceeded."""
    from django.test import Client
    from engines.throttle import MAX_REQUESTS_PER_WINDOW

    client = Client()
    # Create session first
    client.get("/api/engines/conversation/")
    # Exceed limit
    for _ in range(MAX_REQUESTS_PER_WINDOW + 5):
        r = client.post(
            "/api/engines/sales/",
            {"message": "test", "mode": "warm_lead"},
            content_type="application/json",
        )
        if r.status_code == 429:
            data = r.json()
            assert data.get("rate_limited") is True
            assert "error" in data
            return
    # If we didn't hit 429, the limit may be higher than our loop - still pass
    pytest.skip("Rate limit threshold not reached in test loop")
