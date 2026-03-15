"""
CRM sync service: create/update CRMRecord, append notes, update lead stage, assign owner/queue, link support.
Conversation outcomes sync into CRM. Audit trail via CRMActivityLog and ActionLog.
"""
from typing import Optional

from django.db import transaction

from crm.models import CRMRecord, CRMActivityLog
from audit.models import ActionLog
from core.enums import AuditAction


def get_or_create_crm_record_for_customer(
    customer_id: int,
    *,
    crm_id: Optional[str] = None,
    external_phone: str = "",
    external_email: str = "",
    external_name: str = "",
    actor: str = "",
) -> Optional[CRMRecord]:
    """
    Get existing CRMRecord linked to customer, or create one if none exists.
    Returns None if customer not found.
    """
    from leads.models import Customer

    customer = Customer.objects.filter(id=customer_id).first()
    if not customer:
        return None

    existing = CRMRecord.objects.filter(linked_customer_id=customer_id).order_by("-imported_at").first()
    if existing:
        return existing

    if not crm_id:
        crm_id = f"sync_{customer_id}_{customer.identity_id or 0}"

    if CRMRecord.objects.filter(crm_id=crm_id).exists():
        rec = CRMRecord.objects.get(crm_id=crm_id)
        if rec.linked_customer_id != customer_id:
            rec.linked_customer_id = customer_id
            rec.save(update_fields=["linked_customer_id", "updated_at"])
        return rec

    phone = external_phone or (customer.identity.phone if customer.identity else "")
    email = external_email or (customer.identity.email if customer.identity else "")
    name = external_name or (customer.identity.name if customer.identity else "")

    with transaction.atomic():
        rec = CRMRecord.objects.create(
            crm_id=crm_id,
            external_phone=phone,
            external_email=email,
            external_name=name,
            linked_customer_id=customer_id,
            status="sync_created",
        )
        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.RECORD_CREATED,
            content="CRM record created for sync",
            actor=actor,
            metadata={"customer_id": customer_id},
        )
        ActionLog.objects.create(
            action=AuditAction.CRM_IMPORTED.value,
            actor=actor,
            subject_type="customer",
            subject_id=str(customer_id),
            payload={"crm_record_id": rec.id, "crm_id": crm_id, "event": "sync_created"},
        )
    return rec


def append_note_to_crm(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    note: str,
    actor: str = "ai_system",
) -> bool:
    """
    Append a note to CRM record. Creates record for customer if needed.
    Returns True if successful.
    """
    if not note or not note.strip():
        return False

    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(
            customer_id,
            actor=actor,
        )

    if not rec:
        return False

    with transaction.atomic():
        existing = rec.notes or ""
        new_note = f"{note.strip()}\n" if existing else note.strip()
        rec.notes = (existing + "\n" + new_note).strip() if existing else new_note
        rec.save(update_fields=["notes", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.NOTE_ADDED,
            content=note[:500],
            actor=actor,
            metadata={"source": "conversation_sync"},
        )
    return True


def update_lead_stage(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    lead_stage: str,
    actor: str = "ai_system",
) -> bool:
    """Update lead stage on CRM record."""
    if not lead_stage or not lead_stage.strip():
        return False

    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)

    if not rec:
        return False

    old_stage = rec.lead_stage or ""
    with transaction.atomic():
        rec.lead_stage = lead_stage.strip()
        rec.save(update_fields=["lead_stage", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.STAGE_UPDATED,
            content=f"{old_stage} → {rec.lead_stage}",
            actor=actor,
            metadata={"old": old_stage, "new": rec.lead_stage},
        )
    return True


def assign_owner(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    owner: str,
    actor: str = "ai_system",
) -> bool:
    """Assign owner to CRM record."""
    if not owner or not owner.strip():
        return False

    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)

    if not rec:
        return False

    with transaction.atomic():
        rec.owner = owner.strip()
        rec.save(update_fields=["owner", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.OWNER_ASSIGNED,
            content=rec.owner,
            actor=actor,
        )
    return True


def assign_queue(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    queue: str,
    actor: str = "ai_system",
) -> bool:
    """Assign queue to CRM record."""
    if not queue or not queue.strip():
        return False

    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)

    if not rec:
        return False

    with transaction.atomic():
        rec.assigned_queue = queue.strip()
        rec.save(update_fields=["assigned_queue", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.QUEUE_ASSIGNED,
            content=rec.assigned_queue,
            actor=actor,
        )
    return True


def link_support_case(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    support_case_id: int,
    actor: str = "ai_system",
) -> bool:
    """Link support case to CRM record."""
    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)

    if not rec:
        return False

    with transaction.atomic():
        rec.support_case_id = support_case_id
        rec.save(update_fields=["support_case_id", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.SUPPORT_LINKED,
            content=f"Support case #{support_case_id}",
            actor=actor,
            metadata={"support_case_id": support_case_id},
        )
    return True


def update_tags(
    crm_record_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    *,
    tags: Optional[list] = None,
    tags_add: Optional[list] = None,
    actor: str = "ai_system",
) -> bool:
    """
    Update tags on CRM record. Use tags to replace, or tags_add to merge.
    Deduplicates and keeps string tags.
    """
    if tags is None and tags_add is None:
        return False
    if tags is not None and not isinstance(tags, (list, tuple)):
        return False

    rec = None
    if crm_record_id:
        rec = CRMRecord.objects.filter(id=crm_record_id).first()
    if not rec and customer_id:
        rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)

    if not rec:
        return False

    existing = list(rec.tags or [])
    if tags is not None:
        new_tags = [str(t).strip() for t in tags if t and str(t).strip()]
    else:
        add_list = [str(t).strip() for t in (tags_add or []) if t and str(t).strip()]
        seen = set(existing)
        for t in add_list:
            if t and t not in seen:
                existing.append(t)
                seen.add(t)
        new_tags = existing

    seen = set()
    deduped = []
    for t in new_tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    with transaction.atomic():
        rec.tags = deduped
        rec.save(update_fields=["tags", "updated_at"])

        CRMActivityLog.objects.create(
            crm_record=rec,
            activity_type=CRMActivityLog.ActivityType.TAGS_UPDATED,
            content=",".join(deduped[:10]) + ("..." if len(deduped) > 10 else ""),
            actor=actor,
            metadata={"tags": deduped, "count": len(deduped)},
        )
    return True


def sync_conversation_outcome(
    customer_id: int,
    *,
    note: Optional[str] = None,
    lead_stage: Optional[str] = None,
    owner: Optional[str] = None,
    queue: Optional[str] = None,
    tags: Optional[list[str]] = None,
    tags_add: Optional[list[str]] = None,
    actor: str = "ai_system",
) -> Optional[CRMRecord]:
    """
    Sync conversation outcomes to CRM. Creates record if needed, updates fields, logs activity.
    Duplicate protection: one CRMRecord per customer; reuses existing linked record.
    """
    rec = get_or_create_crm_record_for_customer(customer_id, actor=actor)
    if not rec:
        return None

    actions = []
    if note:
        append_note_to_crm(crm_record_id=rec.id, note=note, actor=actor)
        actions.append("note")
    if lead_stage:
        update_lead_stage(crm_record_id=rec.id, lead_stage=lead_stage, actor=actor)
        actions.append("lead_stage")
    if owner:
        assign_owner(crm_record_id=rec.id, owner=owner, actor=actor)
        actions.append("owner")
    if queue:
        assign_queue(crm_record_id=rec.id, queue=queue, actor=actor)
        actions.append("queue")
    if tags or tags_add:
        update_tags(crm_record_id=rec.id, tags=tags, tags_add=tags_add, actor=actor)
        actions.append("tags")

    try:
        from core.observability import log_crm_sync
        log_crm_sync(customer_id=customer_id, action="sync_conversation_outcome", actions=actions)
    except ImportError:
        pass

    return rec
