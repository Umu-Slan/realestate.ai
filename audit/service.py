"""
Audit logging service. Every orchestration run must be auditable.
"""
from typing import Optional

from audit.models import ActionLog


def log(
    action: str,
    actor: str = "",
    subject_type: str = "",
    subject_id: str = "",
    payload: Optional[dict] = None,
    reason: str = "",
    correlation_id: str = "",
    run_id: str = "",
    conversation_id: Optional[int] = None,
) -> ActionLog:
    """Create immutable audit record. Enrich payload with tracing IDs when provided."""
    p = dict(payload or {})
    if correlation_id:
        p["correlation_id"] = correlation_id
    if run_id:
        p["run_id"] = run_id
    if conversation_id is not None:
        p["conversation_id"] = conversation_id
    return ActionLog.objects.create(
        action=str(action),
        actor=actor,
        subject_type=subject_type,
        subject_id=str(subject_id) if subject_id else "",
        payload=p,
        reason=reason,
    )
