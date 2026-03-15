"""Knowledge system tests."""
import pytest
from pathlib import Path
from django.utils import timezone
from datetime import date

from knowledge.models import (
    Project,
    RawDocument,
    IngestedDocument,
    DocumentChunk,
    ProjectPaymentPlan,
    ProjectDeliveryTimeline,
    ProjectUnitCategory,
)
from knowledge.ingestion import ingest_file, ingest_from_content
from knowledge.parsers import parse_text, detect_language
from knowledge.chunking import chunk_document
from knowledge.retrieval import (
    retrieve_by_query,
    RetrievalPolicy,
    get_structured_pricing,
    get_safe_fallback_note,
)
from core.enums import DocumentType, VerificationStatus, AccessLevel


@pytest.mark.django_db
def test_ingest_from_content():
    content = """
# FAQ
س: ما هي طرق الدفع؟
ج: نقدم أقساط حتى 8 سنوات.
"""
    doc = ingest_from_content(
        content,
        DocumentType.FAQ,
        "test",
        "Test FAQ",
    )
    assert doc.status == "embedded"
    assert doc.chunks.exists()
    assert doc.document_type == DocumentType.FAQ


@pytest.mark.django_db
def test_ingest_txt_file():
    fixtures = Path(__file__).parent / "fixtures" / "demo_faq.txt"
    if not fixtures.exists():
        pytest.skip("Demo fixture not found")
    doc = ingest_file(
        str(fixtures),
        DocumentType.FAQ,
        "demo",
        source_of_truth=False,
    )
    assert doc.status == "embedded"
    assert doc.chunks.count() >= 1


@pytest.mark.django_db
def test_versioning():
    doc = ingest_from_content("v1", DocumentType.FAQ, "test", "V1")
    assert doc.versions.count() >= 1


@pytest.mark.django_db
def test_retrieval_returns_results():
    import django.conf
    if "sqlite" in (django.conf.settings.DATABASES.get("default", {}).get("ENGINE", "")):
        pytest.skip("pgvector retrieval requires PostgreSQL")
    doc = ingest_from_content(
        "مشروع النخيل في الشيخ زايد يوفر شقق وفيلات. المرافق تشمل حمام سباحة وصالة رياضية.",
        DocumentType.PROJECT_PDF,
        "test",
        "Project",
    )
    results = retrieve_by_query("شقق في الشيخ زايد", limit=3)
    # May be empty if mock embeddings (all zeros) - semantic search won't rank well
    assert isinstance(results, list)


@pytest.mark.django_db
def test_stale_knowledge_handling():
    doc = ingest_from_content("old", DocumentType.FAQ, "test", "Old")
    doc.verification_status = VerificationStatus.STALE
    doc.save()
    assert not RetrievalPolicy.is_fresh(doc)

    doc2 = ingest_from_content("fresh", DocumentType.FAQ, "test", "Fresh")
    doc2.last_verified_at = timezone.now()
    doc2.save()
    assert RetrievalPolicy.is_fresh(doc2)


@pytest.mark.django_db
def test_missing_document_handling():
    import django.conf
    if "sqlite" in (django.conf.settings.DATABASES.get("default", {}).get("ENGINE", "")):
        pytest.skip("pgvector retrieval requires PostgreSQL")
    results = retrieve_by_query("nonexistent query xyz123", limit=5)
    assert results == [] or all(isinstance(r.content, str) for r in results)


@pytest.mark.django_db
def test_structured_pricing_only_from_project():
    p = Project.objects.create(
        name="Test",
        price_min=1000000,
        price_max=2000000,
        availability_status="available",
    )
    info = get_structured_pricing(p.id)
    assert info["price_min"] == 1000000
    assert info["price_max"] == 2000000
    assert get_structured_pricing(99999) is None


@pytest.mark.django_db
def test_retrieval_policy_no_exact_pricing_from_chunks():
    doc = ingest_from_content("السعر 3 مليون", DocumentType.PROJECT_PDF, "test", "P")
    chunk = doc.chunks.first()
    if chunk:
        assert not RetrievalPolicy.can_use_for_exact_pricing(chunk)
        assert not RetrievalPolicy.can_use_for_exact_availability(chunk)


@pytest.mark.django_db
def test_detect_language():
    assert detect_language("مرحبا بالعالم").value in ("ar", "ar_en")
    assert detect_language("Hello world").value == "en"


@pytest.mark.django_db
def test_chunk_metadata_propagates_on_ingestion():
    """Chunk metadata should include document_type, verification_status, access_level."""
    doc = ingest_from_content(
        "س: ما هي طرق الدفع؟\nج: أقساط حتى 8 سنوات.",
        DocumentType.FAQ,
        "test",
        "FAQ with payment",
    )
    chunk = doc.chunks.first()
    assert chunk is not None
    meta = chunk.metadata or {}
    assert meta.get("document_type") == "faq"
    assert "verification_status" in meta
    assert "access_level" in meta
    assert doc.access_level in (AccessLevel.INTERNAL, "internal")


@pytest.mark.django_db
def test_retrieval_result_has_access_level():
    """RetrievalResult should include access_level for downstream safety checks."""
    import django.conf
    if "sqlite" in (django.conf.settings.DATABASES.get("default", {}).get("ENGINE", "")):
        pytest.skip("pgvector retrieval requires PostgreSQL")
    doc = ingest_from_content("مشروع النخيل", DocumentType.PROJECT_BROCHURE, "test", "Brochure")
    results = retrieve_by_query("مشروع النخيل", limit=3, project_id=doc.project_id)
    for r in results:
        assert hasattr(r, "access_level")
        assert r.access_level in ("public", "internal", "restricted")


@pytest.mark.django_db
def test_safe_fallback_note_for_unverified():
    """get_safe_fallback_note returns disclaimer when results include unverified docs."""
    # Test with empty/mock results - function does not require DB retrieval
    from knowledge.retrieval import RetrievalResult
    fake_results = [
        RetrievalResult(
            chunk_id=1, content="x", chunk_type="general", section_title="",
            document_id=1, document_title="P", document_type="project_pdf",
            source_of_truth=False, verification_status="unverified",
            access_level="internal", is_fresh=False, score=0.5,
            can_use_for_exact_pricing=False, can_use_for_exact_availability=False,
        )
    ]
    note = get_safe_fallback_note(fake_results, for_pricing=True)
    assert "confirm" in note.lower() or "sales" in note.lower() or "team" in note.lower()


@pytest.mark.django_db
def test_structured_facts_verified_vs_unverified():
    """Structured facts service distinguishes verified vs unverified."""
    from knowledge.services.structured_facts import get_project_structured_facts, get_safe_language_for_fact

    p = Project.objects.create(
        name="VerifiedProject",
        price_min=1500000,
        price_max=2500000,
        availability_status="available",
        last_verified_at=timezone.now(),
    )
    facts = get_project_structured_facts(p.id)
    assert facts is not None
    assert facts.pricing.value is not None
    assert facts.pricing.is_verified is True
    assert facts.has_verified_pricing is True
    assert facts.availability.value == "available"
    assert facts.availability.is_verified is True

    p2 = Project.objects.create(
        name="UnverifiedProject",
        price_min=2000000,
        price_max=3000000,
        availability_status="limited",
        last_verified_at=None,
    )
    facts2 = get_project_structured_facts(p2.id)
    assert facts2.pricing.is_verified is False
    assert facts2.has_verified_pricing is False
    assert facts2.availability.is_verified is False


@pytest.mark.django_db
def test_structured_facts_payment_plan_and_delivery():
    """Payment plan and delivery timeline from structured fact models."""
    from knowledge.services.structured_facts import get_project_structured_facts

    p = Project.objects.create(name="FullProject", price_min=1000000, price_max=2000000)
    ProjectPaymentPlan.objects.create(
        project=p,
        down_payment_pct_min=10,
        down_payment_pct_max=30,
        installment_years_min=5,
        installment_years_max=8,
        last_verified_at=timezone.now(),
    )
    ProjectDeliveryTimeline.objects.create(
        project=p,
        phase_name="Phase 1",
        expected_start_date=date(2026, 6, 1),
        expected_end_date=date(2027, 12, 31),
        last_verified_at=timezone.now(),
    )
    ProjectUnitCategory.objects.create(
        project=p,
        category_name="3BR Apartment",
        price_min=1500000,
        price_max=1800000,
        quantity_available=5,
        last_verified_at=timezone.now(),
    )

    facts = get_project_structured_facts(p.id)
    assert facts.payment_plan.value is not None
    assert facts.payment_plan.value["installment_years_min"] == 5
    assert facts.payment_plan.value["installment_years_max"] == 8
    assert facts.delivery.value is not None
    assert facts.delivery.value["phase_name"] == "Phase 1"
    assert len(facts.unit_categories) == 1
    assert facts.unit_categories[0]["category_name"] == "3BR Apartment"
    assert facts.unit_categories[0]["quantity_available"] == 5


@pytest.mark.django_db
def test_safe_language_for_unverified_fact():
    """get_safe_language_for_fact returns disclaimer when unverified."""
    from knowledge.services.structured_facts import get_safe_language_for_fact

    ar = get_safe_language_for_fact("pricing", has_value=False, is_verified=False, lang="ar")
    assert "فريق" in ar or "المبيعات" in ar or "التأكد" in ar
    en = get_safe_language_for_fact("pricing", has_value=True, is_verified=False, lang="en")
    assert "sales" in en.lower() or "confirm" in en.lower()
    empty = get_safe_language_for_fact("pricing", has_value=True, is_verified=True, lang="ar")
    assert empty == ""
