"""
Base CRM adapter interface. Future connectors implement this.
"""
from typing import Iterator, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CRMLeadRow:
    """Normalized CRM lead row - internal format regardless of source."""

    crm_id: str
    name: str
    phone: str
    email: str
    username: str
    source: str
    campaign: str
    historical_classification: str
    historical_score: Optional[int]
    notes: str
    project_interest: str
    status: str
    crm_created_at: Optional[datetime]
    crm_updated_at: Optional[datetime]
    raw: dict
    # Richer mapping
    owner: str = ""
    lead_stage: str = ""
    tags: list = field(default_factory=list)


class BaseCRMAdapter:
    """Interface for CRM data connectors."""

    def iter_leads(self, file_path: str, **kwargs) -> Iterator[CRMLeadRow]:
        """Yield normalized CRMLeadRow from source. Raises on corrupt/unsupported."""
        raise NotImplementedError

    def validate_row(self, row: CRMLeadRow) -> tuple[bool, str]:
        """Return (is_valid, error_message)."""
        if not row.crm_id or not row.crm_id.strip():
            return False, "crm_id required"
        if not row.phone and not row.email and not row.username:
            return False, "At least one of phone, email, username required"
        return True, ""
