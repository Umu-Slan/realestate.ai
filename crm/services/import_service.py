"""
CRM import service: normalize, validate, resolve identity, create/update domain models.
"""
import uuid
from pathlib import Path

from django.db import transaction

from crm.models import CRMRecord, CRMImportBatch
from crm.adapters.csv_adapter import CSVCRMAdapter
from crm.adapters.excel_adapter import ExcelCRMAdapter
from crm.adapters.base import CRMLeadRow
from leads.models import CustomerIdentity, Customer, LeadProfile
from leads.services.identity_resolution import resolve_identity
from core.enums import SourceChannel
from audit.models import ActionLog
from core.enums import AuditAction


def normalize_phone(phone: str) -> str:
    """Normalize Egyptian phone for matching."""
    if not phone:
        return ""
    s = "".join(c for c in phone if c.isdigit())
    if s.startswith("2"):  # country code
        s = s[1:]
    if s.startswith("0"):
        s = s[1:]
    if len(s) == 9 and s.startswith("1"):  # 01xxxxxxxx
        return s
    if len(s) == 10 and s.startswith("01"):
        return s[2:]
    return s[-9:] if len(s) >= 9 else s


def normalize_email(email: str) -> str:
    """Lowercase, strip."""
    if not email:
        return ""
    return email.lower().strip()


def normalize_name(name: str) -> str:
    """Strip, collapse whitespace."""
    if not name:
        return ""
    return " ".join(name.split())


def get_adapter(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return CSVCRMAdapter()
    if ext in (".xlsx", ".xls"):
        return ExcelCRMAdapter()
    raise ValueError(f"Unsupported format: {ext}")


def _default_summary(batch_id: str, error: str = "") -> dict:
    """Always produce a summary report - acceptance criteria."""
    return {
        "total_rows": 0,
        "imported": 0,
        "duplicates": 0,
        "conflicts": 0,
        "errors": 1 if error else 0,
        "batch_id": batch_id,
        "status": "failed" if error else "completed",
        "error": error[:500] if error else "",
    }


@transaction.atomic
def import_crm_file(
    file_path: str,
    *,
    dry_run: bool = False,
    actor: str = "",
    auto_merge_threshold: float = 0.95,
) -> dict:
    """
    Import CRM file. Returns summary with counts. Graceful handling for malformed files.
    """
    batch_id = str(uuid.uuid4())[:8]
    stats = {
        "total_rows": 0,
        "imported": 0,
        "duplicates": 0,
        "conflicts": 0,
        "errors": 0,
        "batch_id": batch_id,
        "status": "completed",
    }

    try:
        adapter = get_adapter(file_path)
    except ValueError as e:
        return _default_summary(batch_id, f"Unsupported format or malformed file: {e}")
    except Exception as e:
        return _default_summary(batch_id, f"File read error: {e}")

    batch = CRMImportBatch.objects.create(
        batch_id=batch_id,
        file_name=Path(file_path).name,
        total_rows=0,
        status="in_progress",
    )

    seen_crm_ids = set()

    try:
        rows_iter = adapter.iter_leads(file_path)
    except Exception as e:
        batch.total_rows = 0
        batch.error_count = 1
        batch.status = "failed"
        batch.save()
        return _default_summary(batch_id, f"Parse error: {e}")

    for row in rows_iter:
        stats["total_rows"] += 1
        is_valid, err = adapter.validate_row(row)
        if not is_valid:
            stats["errors"] += 1
            continue

        if row.crm_id in seen_crm_ids:
            stats["duplicates"] += 1
            continue
        seen_crm_ids.add(row.crm_id)

        try:
            result = _process_row(
                row,
                batch_id=batch_id,
                auto_merge_threshold=auto_merge_threshold,
            )
            if result == "imported":
                stats["imported"] += 1
            elif result == "duplicate":
                stats["duplicates"] += 1
            elif result == "conflict":
                stats["conflicts"] += 1
        except Exception as e:
            stats["errors"] += 1
            if dry_run:
                raise

    batch.total_rows = stats["total_rows"]
    batch.imported_count = stats["imported"]
    batch.duplicate_count = stats["duplicates"]
    batch.conflict_count = stats["conflicts"]
    batch.error_count = stats["errors"]
    batch.status = "cancelled" if dry_run else "completed"
    batch.save()

    if dry_run:
        transaction.set_rollback(True)
        return stats

    ActionLog.objects.create(
        action=AuditAction.CRM_IMPORTED.value,
        actor=actor,
        subject_type="crm_import_batch",
        subject_id=batch_id,
        payload=stats,
    )
    return stats


def _process_row(
    row: CRMLeadRow,
    *,
    batch_id: str,
    auto_merge_threshold: float,
) -> str:
    """Process single row. Returns: imported | duplicate | conflict."""
    if CRMRecord.objects.filter(crm_id=row.crm_id).exists():
        return "duplicate"

    match_result = resolve_identity(
        phone=row.phone or None,
        email=row.email or None,
        external_id=row.crm_id,
        username=row.username or None,
        name=row.name or None,
        auto_merge_threshold=auto_merge_threshold,
    )

    if match_result.matched:
        identity = match_result.identity
        if match_result.manual_review_required:
            return "conflict"
    else:
        identity = CustomerIdentity.objects.create(
            external_id=row.crm_id,
            phone=row.phone,
            email=row.email,
            name=row.name,
            metadata={"username": row.username} if row.username else {},
        )

    customer, _ = Customer.objects.get_or_create(
        identity=identity,
        defaults={"source_channel": SourceChannel.CRM_IMPORT},
    )

    LeadProfile.objects.update_or_create(
        customer=customer,
        defaults={
            "project_interest": row.project_interest,
            "source_channel": SourceChannel.CRM_IMPORT,
            "metadata": {"campaign": row.campaign, "source": row.source} if row.source or row.campaign else {},
        },
    )

    CRMRecord.objects.create(
        crm_id=row.crm_id,
        external_phone=row.phone,
        external_email=row.email,
        external_name=row.name,
        external_username=row.username,
        source=row.source,
        campaign=row.campaign,
        historical_classification=row.historical_classification,
        historical_score=row.historical_score,
        notes=row.notes,
        project_interest=row.project_interest,
        status=row.status,
        crm_created_at=row.crm_created_at,
        crm_updated_at=row.crm_updated_at,
        source_channel=SourceChannel.CRM_IMPORT,
        raw_data=row.raw,
        import_batch_id=batch_id,
        linked_customer_id=customer.id,
        owner=getattr(row, "owner", "") or "",
        lead_stage=getattr(row, "lead_stage", "") or row.status or "",
        tags=getattr(row, "tags", None) or [],
    )
    return "imported"
