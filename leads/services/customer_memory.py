"""
Unified Customer Memory: short-term (conversation context) and long-term.
"""
from django.db import models
from django.utils import timezone

from leads.models import Customer, CustomerMemory
from core.enums import MemoryType


def add_memory(
    customer: Customer,
    memory_type: str,
    content: str,
    source: str = "",
    source_id: str = "",
    metadata: dict | None = None,
    expires_at=None,
) -> CustomerMemory:
    """Add long-term memory item."""
    return CustomerMemory.objects.create(
        customer=customer,
        memory_type=memory_type,
        content=content,
        source=source,
        source_id=source_id,
        metadata=metadata or {},
        expires_at=expires_at,
    )


def get_long_term_memory(customer: Customer, limit: int = 50) -> list[dict]:
    """Retrieve non-expired long-term memories."""
    now = timezone.now()
    qs = customer.memories.filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
    ).order_by("-created_at")[:limit]
    return [
        {
            "id": m.id,
            "memory_type": m.memory_type,
            "content": m.content,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
        }
        for m in qs
    ]


def get_short_term_context(customer: Customer, conversation_id: int | None = None) -> dict:
    """
    Short-term: current conversation messages (fetched elsewhere).
    This returns recent memories and a summary hook for conversation context.
    """
    from leads.services.timeline import build_timeline
    timeline = build_timeline(customer, limit=5)
    return {
        "recent_timeline_preview": timeline[:3],
        "memory_count": customer.memories.count(),
    }


