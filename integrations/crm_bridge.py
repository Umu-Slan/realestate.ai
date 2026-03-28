"""
Bridge from internal CRM sync to the company's external systems.
Configured via EXTERNAL_CRM_PUSH_* settings — see config/settings.py.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def push_conversation_sync_to_external_crm(
    crm_record_id: int,
    *,
    note: Optional[str] = None,
    lead_stage: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[list] = None,
) -> Any:
    """
    After internal CRMRecord is updated from orchestration, optionally notify the company's CRM stack.
    No-op when EXTERNAL_CRM_PUSH_ENABLED is False or mode is stub.
    """
    if not getattr(settings, "EXTERNAL_CRM_PUSH_ENABLED", False):
        return None

    mode = (getattr(settings, "EXTERNAL_CRM_PUSH_MODE", "stub") or "stub").strip().lower()
    if mode == "stub":
        return None

    if mode == "webhook":
        from crm.adapters.webhook_outbound import WebhookCRMOutboundAdapter

        adapter = WebhookCRMOutboundAdapter()
        return adapter.push_record(
            crm_record_id,
            note=note,
            lead_stage=lead_stage,
            owner=owner,
            tags=tags,
        )

    logger.warning("Unknown EXTERNAL_CRM_PUSH_MODE=%s — skipping outbound CRM", mode)
    return None
