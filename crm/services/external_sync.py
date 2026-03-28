"""
Inbound CRM events from the company's external system (HubSpot, Zoho, custom ERP, etc.).
Upserts CRMRecord + customer graph using the same identity rules as CSV import.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from django.db import transaction

from crm.adapters.base import CRMLeadRow
from crm.models import CRMRecord, CRMActivityLog
from crm.services.import_service import _process_row
from audit.models import ActionLog
from core.enums import AuditAction


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _payload_to_lead_row(data: dict) -> CRMLeadRow:
    tags = data.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif not isinstance(tags, list):
        tags = []
    return CRMLeadRow(
        crm_id=str(data.get("crm_id", "")).strip(),
        name=str(data.get("name", "") or "").strip(),
        phone=str(data.get("phone", "") or "").strip(),
        email=str(data.get("email", "") or "").strip(),
        username=str(data.get("username", "") or "").strip(),
        source=str(data.get("source", "") or "").strip(),
        campaign=str(data.get("campaign", "") or "").strip(),
        historical_classification=str(data.get("historical_classification", "") or "").strip(),
        historical_score=data.get("historical_score"),
        notes=str(data.get("notes", "") or "").strip(),
        project_interest=str(data.get("project_interest", "") or "").strip(),
        status=str(data.get("status", "") or "").strip(),
        crm_created_at=_parse_dt(data.get("crm_created_at")),
        crm_updated_at=_parse_dt(data.get("crm_updated_at")),
        raw=dict(data.get("raw") or data),
        owner=str(data.get("owner", "") or "").strip(),
        lead_stage=str(data.get("lead_stage", "") or data.get("status", "") or "").strip(),
        tags=tags,
    )


@transaction.atomic
def upsert_crm_lead_from_payload(
    data: dict,
    *,
    actor: str = "external_crm",
    auto_merge_threshold: float = 0.95,
) -> dict:
    """
    Create or update a lead from JSON (webhook body).

    Required: crm_id
    Recommended: at least one of phone, email, username (same validation as CSV rows).

    Returns: { "status": "imported"|"updated"|"duplicate"|"conflict"|"error", ... }
    """
    row = _payload_to_lead_row(data)
    if not row.crm_id:
        return {"status": "error", "error": "crm_id is required"}

    existing = CRMRecord.objects.filter(crm_id=row.crm_id).first()
    if existing:
        return _merge_into_existing_record(existing, row, actor=actor)

    from crm.adapters.base import BaseCRMAdapter

    adapter = BaseCRMAdapter()
    is_valid, verr = adapter.validate_row(row)
    if not is_valid:
        return {"status": "error", "error": verr}

    batch_id = f"evt_{uuid.uuid4().hex[:12]}"
    try:
        outcome = _process_row(row, batch_id=batch_id, auto_merge_threshold=auto_merge_threshold)
    except Exception as e:
        return {"status": "error", "error": str(e)[:500]}

    rec = CRMRecord.objects.filter(crm_id=row.crm_id).first()
    ActionLog.objects.create(
        action=AuditAction.CRM_IMPORTED.value,
        actor=actor,
        subject_type="crm_webhook",
        subject_id=row.crm_id,
        payload={"batch_id": batch_id, "outcome": outcome},
    )
    return {
        "status": outcome,
        "crm_id": row.crm_id,
        "crm_record_id": rec.id if rec else None,
        "customer_id": rec.linked_customer_id if rec else None,
    }


def _merge_into_existing_record(rec: CRMRecord, row: CRMLeadRow, *, actor: str) -> dict:
    """Apply non-empty fields from webhook onto an existing CRMRecord."""
    if row.name:
        rec.external_name = row.name
    if row.phone:
        rec.external_phone = row.phone
    if row.email:
        rec.external_email = row.email
    if row.username:
        rec.external_username = row.username
    if row.source:
        rec.source = row.source
    if row.campaign:
        rec.campaign = row.campaign
    if row.historical_classification:
        rec.historical_classification = row.historical_classification
    if row.historical_score is not None:
        rec.historical_score = row.historical_score
    if row.project_interest:
        rec.project_interest = row.project_interest
    if row.status:
        rec.status = row.status
    if row.owner:
        rec.owner = row.owner
    if row.lead_stage:
        rec.lead_stage = row.lead_stage
    if row.tags:
        seen = set(rec.tags or [])
        merged = list(rec.tags or [])
        for t in row.tags:
            if t and t not in seen:
                merged.append(t)
                seen.add(t)
        rec.tags = merged
    if row.notes:
        base = (rec.notes or "").strip()
        rec.notes = f"{base}\n{row.notes}".strip() if base else row.notes
    if row.crm_updated_at:
        rec.crm_updated_at = row.crm_updated_at
    rec.raw_data = {**(rec.raw_data or {}), **(row.raw or {})}
    rec.save()

    CRMActivityLog.objects.create(
        crm_record=rec,
        activity_type=CRMActivityLog.ActivityType.NOTE_ADDED,
        content=f"external sync by {actor}",
        actor=actor,
        metadata={"event": "webhook_upsert"},
    )
    return {
        "status": "updated",
        "crm_id": rec.crm_id,
        "crm_record_id": rec.id,
        "customer_id": rec.linked_customer_id,
    }
