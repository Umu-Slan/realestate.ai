"""
CSV CRM adapter - maps common column names to normalized fields.
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseCRMAdapter, CRMLeadRow


# Flexible column mapping: external name -> internal field
COLUMN_ALIASES = {
    "crm_id": ["crm_id", "id", "lead_id", "external_id"],
    "name": ["name", "lead_name", "full_name", "contact_name"],
    "phone": ["phone", "mobile", "tel", "phone_number", "رقم_الموبايل"],
    "email": ["email", "email_address", "mail"],
    "username": ["username", "user", "user_id"],
    "source": ["source", "lead_source", "origin"],
    "campaign": ["campaign", "utm_campaign", "marketing_campaign"],
    "historical_classification": ["historical_classification", "classification", "type", "lead_type", "qualification"],
    "historical_score": ["historical_score", "score", "lead_score", "rating"],
    "notes": ["notes", "note", "comments", "description"],
    "project_interest": ["project_interest", "project", "interested_project", "مشروع_الاهتمام"],
    "status": ["status", "state", "lead_status", "stage"],
    "crm_created_at": ["crm_created_at", "created_at", "created", "date_created"],
    "crm_updated_at": ["crm_updated_at", "updated_at", "updated", "modified"],
    "owner": ["owner", "assigned_to", "sales_rep", "responsible", "معرف"],
    "lead_stage": ["lead_stage", "stage", "lead_status", "مرحلة_العملاء"],
    "tags": ["tags", "tag", "labels", "categories"],
}


def _find_value(row: dict, field: str) -> str:
    """Find value by field or alias. Case-insensitive key match."""
    row_lower = {k.strip().lower(): (k, v) for k, v in row.items()}
    for alias in COLUMN_ALIASES.get(field, [field]):
        for k, (orig_key, v) in row_lower.items():
            if alias.lower() in k or k == alias.lower():
                return str(v).strip() if v is not None else ""
    return ""


def _parse_datetime(s: str) -> Optional[datetime]:
    if not s or not s.strip():
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s.strip()[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


class CSVCRMAdapter(BaseCRMAdapter):
    """CSV file adapter with flexible column mapping."""

    def iter_leads(self, file_path: str, **kwargs) -> Iterator[CRMLeadRow]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                crm_id = _find_value(row, "crm_id") or f"row_{i+1}"
                created_s = _find_value(row, "crm_created_at")
                updated_s = _find_value(row, "crm_updated_at")
                score_s = _find_value(row, "historical_score")
                try:
                    score = int(score_s) if score_s else None
                except (ValueError, TypeError):
                    score = None
                tags_s = _find_value(row, "tags")
                tags = [t.strip() for t in tags_s.split(",") if t.strip()] if tags_s else []
                yield CRMLeadRow(
                    crm_id=crm_id,
                    name=_find_value(row, "name"),
                    phone=_find_value(row, "phone"),
                    email=_find_value(row, "email"),
                    username=_find_value(row, "username"),
                    source=_find_value(row, "source"),
                    campaign=_find_value(row, "campaign"),
                    historical_classification=_find_value(row, "historical_classification"),
                    historical_score=score,
                    notes=_find_value(row, "notes"),
                    project_interest=_find_value(row, "project_interest"),
                    status=_find_value(row, "status"),
                    crm_created_at=_parse_datetime(created_s),
                    crm_updated_at=_parse_datetime(updated_s),
                    raw=dict(row),
                    owner=_find_value(row, "owner"),
                    lead_stage=_find_value(row, "lead_stage") or _find_value(row, "status"),
                    tags=tags,
                )
