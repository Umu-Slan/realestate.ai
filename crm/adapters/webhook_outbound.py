"""
Push CRMRecord snapshots to the company's HTTP endpoint (Zapier, n8n, custom middleware, HubSpot workflow URL, etc.).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from django.conf import settings

from crm.adapters.outbound import BaseCRMOutboundAdapter, CRMOutboundResult
from crm.models import CRMRecord

logger = logging.getLogger(__name__)


def _record_payload(rec: CRMRecord) -> dict[str, Any]:
    return {
        "crm_id": rec.crm_id,
        "external_phone": rec.external_phone,
        "external_email": rec.external_email,
        "external_name": rec.external_name,
        "external_username": rec.external_username,
        "source": rec.source,
        "campaign": rec.campaign,
        "lead_stage": rec.lead_stage,
        "status": rec.status,
        "owner": rec.owner,
        "assigned_queue": rec.assigned_queue,
        "tags": rec.tags or [],
        "notes": rec.notes,
        "project_interest": rec.project_interest,
        "linked_customer_id": rec.linked_customer_id,
        "historical_classification": rec.historical_classification,
        "historical_score": rec.historical_score,
    }


class WebhookCRMOutboundAdapter(BaseCRMOutboundAdapter):
    """POST JSON to EXTERNAL_CRM_WEBHOOK_URL with optional Bearer secret."""

    vendor_name = "webhook"

    def push_record(
        self,
        crm_record_id: int,
        *,
        note: Optional[str] = None,
        lead_stage: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> CRMOutboundResult:
        url = (getattr(settings, "EXTERNAL_CRM_WEBHOOK_URL", None) or "").strip()
        if not url:
            return CRMOutboundResult(success=False, error="EXTERNAL_CRM_WEBHOOK_URL is not set")

        rec = CRMRecord.objects.filter(pk=crm_record_id).first()
        if not rec:
            return CRMOutboundResult(success=False, error="CRMRecord not found")

        body = {
            "event": "ai_crm_sync",
            "crm_record_id": rec.id,
            "record": _record_payload(rec),
            "delta": {
                k: v
                for k, v in {
                    "note": note,
                    "lead_stage": lead_stage,
                    "owner": owner,
                    "tags": tags,
                }.items()
                if v is not None
            },
        }

        headers = {"Content-Type": "application/json"}
        secret = (getattr(settings, "EXTERNAL_CRM_WEBHOOK_SECRET", None) or "").strip()
        if secret:
            headers["Authorization"] = f"Bearer {secret}"

        timeout = float(getattr(settings, "EXTERNAL_CRM_WEBHOOK_TIMEOUT", 15))
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            logger.warning("External CRM webhook failed: %s", e)
            return CRMOutboundResult(success=False, error=str(e)[:300])

        return CRMOutboundResult(success=True, external_id=rec.crm_id)
