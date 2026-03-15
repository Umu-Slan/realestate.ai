"""
Outbound CRM adapter interface - push updates to external CRM vendors.
Implementations: Salesforce, HubSpot, etc. Stub for first company.
Adapter layer only - no business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class CRMOutboundResult:
    """Result of outbound sync attempt."""

    success: bool
    external_id: Optional[str] = None
    error: Optional[str] = None
    synced_at: Optional[str] = None  # ISO timestamp


class BaseCRMOutboundAdapter(ABC):
    """Interface for pushing CRMRecord updates to external CRM."""

    vendor_name: str = "base"

    @abstractmethod
    def push_record(
        self,
        crm_record_id: int,
        *,
        note: Optional[str] = None,
        lead_stage: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> CRMOutboundResult:
        """
        Push CRM record updates to external system.
        Returns result with success, external_id, error.
        """
        raise NotImplementedError


class StubCRMOutboundAdapter(BaseCRMOutboundAdapter):
    """
    Stub adapter - no external push. Use when only internal CRM storage.
    Wire live adapter for Salesforce/HubSpot when ready.
    """

    vendor_name = "stub"

    def push_record(
        self,
        crm_record_id: int,
        *,
        note: Optional[str] = None,
        lead_stage: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> CRMOutboundResult:
        """No-op. Ready for live implementation."""
        return CRMOutboundResult(success=True, external_id=f"stub_{crm_record_id}")
