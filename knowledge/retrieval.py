"""
Hybrid retrieval: semantic + metadata + freshness-aware.
Retrieval policy: descriptive answers may use chunks; exact prices/availability must use structured.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from knowledge.models import DocumentChunk, IngestedDocument, Project
from core.enums import VerificationStatus, ChunkType


@dataclass
class RetrievalResult:
    chunk_id: int
    content: str
    chunk_type: str
    section_title: str
    document_id: int
    document_title: str
    document_type: str
    source_of_truth: bool
    verification_status: str
    access_level: str
    is_fresh: bool
    score: float
    can_use_for_exact_pricing: bool
    can_use_for_exact_availability: bool


class RetrievalPolicy:
    """
    Policy: exact prices/availability must NOT rely only on document chunks.
    Use Project (structured) for that. Chunks are for descriptive content.
    """

    @staticmethod
    def can_use_for_exact_pricing(chunk: DocumentChunk) -> bool:
        return False  # Never use chunks for exact pricing

    @staticmethod
    def can_use_for_exact_availability(chunk: DocumentChunk) -> bool:
        return False  # Never use chunks for exact availability

    @staticmethod
    def is_fresh(doc: IngestedDocument, max_stale_days: int = 90) -> bool:
        if doc.verification_status == VerificationStatus.STALE:
            return False
        if doc.validity_window_end and doc.validity_window_end < date.today():
            return False
        if not doc.last_verified_at and not doc.validity_window_end:
            return doc.verification_status != VerificationStatus.SUPERSEDED  # Unverified = assume ok unless superseded
        if doc.last_verified_at:
            delta = timezone.now() - doc.last_verified_at
            return delta.days <= max_stale_days
        return True


def retrieve(
    query_embedding: list[float],
    *,
    document_type: Optional[str] = None,
    document_types: Optional[list[str]] = None,
    chunk_type: Optional[str] = None,
    chunk_types: Optional[list[str]] = None,
    project_id: Optional[int] = None,
    exclude_stale: bool = True,
    limit: int = 10,
) -> list[RetrievalResult]:
    """
    Hybrid retrieval: semantic similarity + metadata filters + freshness ranking.
    Supports document_types (list) for multi-type retrieval; chunk_types for filtering.
    """
    from pgvector.django import L2Distance

    emb = list(query_embedding)  # ensure list for pgvector
    qs = DocumentChunk.objects.select_related("document").filter(
        embedding__isnull=False,
        document__status="embedded",
    )
    dt_filter = document_types if document_types else ([document_type] if document_type else None)
    if dt_filter:
        qs = qs.filter(document__document_type__in=dt_filter)
    ct_filter = chunk_types if chunk_types else ([chunk_type] if chunk_type else None)
    if ct_filter:
        qs = qs.filter(chunk_type__in=ct_filter)
    if project_id:
        qs = qs.filter(document__project_id=project_id)
    if exclude_stale:
        qs = qs.exclude(document__verification_status=VerificationStatus.STALE)
        qs = qs.exclude(
            document__validity_window_end__lt=date.today(),
        )

    # Semantic search
    annotated = qs.annotate(
        distance=L2Distance("embedding", emb)
    ).order_by("distance")[: limit * 2]  # over-fetch for freshness ranking

    results = []
    for chunk in annotated:
        doc = chunk.document
        is_fresh = RetrievalPolicy.is_fresh(doc)
        score = 1.0 / (1.0 + getattr(chunk, "distance", 1.0))
        # Downrank stale
        if not is_fresh:
            score *= 0.5
        results.append(
            RetrievalResult(
                chunk_id=chunk.id,
                content=chunk.content,
                chunk_type=chunk.chunk_type,
                section_title=chunk.section_title or "",
                document_id=doc.id,
                document_title=doc.title,
                document_type=doc.document_type,
                source_of_truth=doc.source_of_truth,
                verification_status=doc.verification_status,
                access_level=getattr(doc, "access_level", "internal"),
                is_fresh=is_fresh,
                score=score,
                can_use_for_exact_pricing=RetrievalPolicy.can_use_for_exact_pricing(chunk),
                can_use_for_exact_availability=RetrievalPolicy.can_use_for_exact_availability(chunk),
            )
        )
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


def get_structured_pricing(project_id: int) -> Optional[dict]:
    """Source of truth for exact pricing. From Project structured fact layer."""
    from knowledge.services.structured_facts import get_project_structured_facts

    facts = get_project_structured_facts(project_id)
    if not facts or not facts.pricing.value:
        if facts:
            return {
                "project_name": facts.project_name,
                "price_min": None,
                "price_max": None,
                "availability_status": facts.availability.value,
                "last_verified_at": None,
                "is_verified": False,
            }
        return None
    pv = facts.pricing.value
    return {
        "project_name": facts.project_name,
        "price_min": pv.get("price_min"),
        "price_max": pv.get("price_max"),
        "availability_status": facts.availability.value,
        "last_verified_at": facts.pricing.last_verified_at,
        "is_verified": facts.pricing.is_verified,
    }


def get_safe_fallback_note(
    results: list["RetrievalResult"],
    *,
    for_pricing: bool = False,
    for_availability: bool = False,
) -> str:
    """
    Return a safe disclaimer when answers rely on unverified document chunks.
    Use when presenting info that must not be stated as exact (pricing/availability).
    """
    if for_pricing or for_availability:
        return (
            "Pricing and availability should be confirmed with our sales team. "
            "The information above is from our knowledge base and may not reflect current offers."
        )
    unverified = [r for r in results if r.verification_status not in ("verified", "pending")]
    if unverified:
        return (
            "Some information above is from documents that have not been formally verified. "
            "Please confirm critical details with our team before making decisions."
        )
    return ""


def get_structured_availability(project_id: int) -> Optional[dict]:
    """Source of truth for exact availability. From structured fact layer."""
    from knowledge.services.structured_facts import get_project_structured_facts

    facts = get_project_structured_facts(project_id)
    if not facts:
        return None
    return {
        "project_name": facts.project_name,
        "availability_status": facts.availability.value,
        "last_verified_at": facts.availability.last_verified_at,
        "is_verified": facts.availability.is_verified,
    }


def retrieve_by_query(
    query_text: str,
    **kwargs,
) -> list[RetrievalResult]:
    """Embed query and retrieve. Convenience wrapper."""
    from knowledge.embedding import get_embedding_client
    client = get_embedding_client()
    embeddings = client.embed([query_text])
    if not embeddings:
        return []
    return retrieve(embeddings[0], **kwargs)
