"""
Customer memory persistence - load/save structured profile.
Uses leads.CustomerMemory with memory_type=PROFILE_UPDATED.
"""
import logging
from typing import Optional

from orchestration.agents.memory_schema import CustomerMemoryProfile

logger = logging.getLogger(__name__)

# MemoryType.PROFILE_UPDATED
_PROFILE_TYPE = "profile_updated"


def _get_customer_from_context(customer_id: Optional[int], identity_id: Optional[int]):
    """Resolve Customer for memory persistence."""
    if customer_id:
        try:
            from leads.models import Customer
            return Customer.objects.filter(pk=customer_id, is_active=True).first()
        except Exception:
            pass
    if identity_id:
        try:
            from leads.models import CustomerIdentity
            identity = CustomerIdentity.objects.filter(pk=identity_id).first()
            if identity:
                return identity.customers.filter(is_active=True).first()
        except Exception:
            pass
    return None


def load_customer_profile(
    customer_id: Optional[int] = None,
    identity_id: Optional[int] = None,
) -> CustomerMemoryProfile:
    """
    Load latest customer memory profile from DB.
    Returns empty profile if not found or no customer.
    """
    customer = _get_customer_from_context(customer_id, identity_id)
    if not customer:
        return CustomerMemoryProfile()

    try:
        from leads.models import CustomerMemory
        from core.enums import MemoryType

        mem = (
            CustomerMemory.objects.filter(
                customer=customer,
                memory_type=MemoryType.PROFILE_UPDATED,
            )
            .order_by("-created_at")
            .first()
        )
        if mem and isinstance(mem.metadata, dict) and mem.metadata:
            return CustomerMemoryProfile.from_dict(mem.metadata)
    except Exception as e:
        logger.warning("Failed to load customer memory: %s", e)
    return CustomerMemoryProfile()


def save_customer_profile(
    profile: CustomerMemoryProfile,
    customer_id: Optional[int] = None,
    identity_id: Optional[int] = None,
    source: str = "memory_agent",
    conversation_id: Optional[int] = None,
) -> bool:
    """
    Persist customer memory profile. Creates new CustomerMemory row (audit trail).
    Returns True if saved.
    """
    customer = _get_customer_from_context(customer_id, identity_id)
    if not customer:
        return False

    try:
        from leads.models import CustomerMemory
        from core.enums import MemoryType

        CustomerMemory.objects.create(
            customer=customer,
            memory_type=MemoryType.PROFILE_UPDATED,
            content="",  # Structured data in metadata
            source=source,
            source_id=str(conversation_id) if conversation_id else "",
            metadata=profile.to_dict(),
        )
        return True
    except Exception as e:
        logger.warning("Failed to save customer memory: %s", e)
        return False
