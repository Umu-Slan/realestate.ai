"""
Document onboarding: save uploaded files, ingest into knowledge, track batch/items.
"""
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.conf import settings

from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType, OnboardingItemStatus
from knowledge.ingestion import ingest_file
from core.enums import DocumentType
from audit.models import ActionLog
from core.enums import AuditAction


def _ensure_upload_dir():
    d = Path(settings.MEDIA_ROOT) / "onboarding" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_uploaded_file(f, upload_dir):
    base = (f.name or "upload")[:200].replace("..", "_")
    path = upload_dir / base
    stem, suf = path.stem, path.suffix
    i = 0
    while path.exists():
        i += 1
        path = upload_dir / ("%s_%s%s" % (stem, i, suf))
    with open(path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)
    return path


def _supported_ext(path):
    return path.suffix.lower() in (
        ".pdf",
        ".csv",
        ".xlsx",
        ".xls",
        ".txt",
        ".md",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".tif",
        ".tiff",
        ".bmp",
    )


def run_document_batch(
    files,
    document_type,
    company_id=None,
    project_id=None,
    source_of_truth=False,
    source_name="onboarding",
    created_by="",
):
    """
    Run document onboarding: save files, ingest each, create batch with items.
    Returns batch with summary counts.
    """
    batch = OnboardingBatch.objects.create(
        company_id=company_id,
        batch_type=OnboardingBatchType.DOCUMENTS,
        status="in_progress",
        created_by=created_by,
    )
    upload_dir = _ensure_upload_dir()
    imported = skipped = failed = 0

    for f in files:
        if not f.name:
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name="(unnamed)",
                status=OnboardingItemStatus.FAILED,
                error_message="No filename",
            )
            failed += 1
            continue

        path = Path(f.name)
        if not _supported_ext(path):
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name=f.name,
                status=OnboardingItemStatus.SKIPPED,
                error_message="Unsupported extension: %s" % path.suffix,
            )
            skipped += 1
            continue

        try:
            saved_path = _save_uploaded_file(f, upload_dir)
        except Exception as e:
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name=f.name,
                status=OnboardingItemStatus.FAILED,
                error_message=str(e)[:500],
            )
            failed += 1
            continue

        try:
            doc = ingest_file(
                str(saved_path),
                document_type=document_type,
                source_name=source_name,
                project_id=project_id,
                company_id=company_id,
                source_of_truth=source_of_truth,
                uploaded_by=created_by,
            )
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name=f.name,
                status=OnboardingItemStatus.SUCCESS,
                document_id=doc.id,
            )
            imported += 1
            ActionLog.objects.create(
                action=AuditAction.KNOWLEDGE_INGESTED.value,
                actor=created_by or "onboarding",
                subject_type="ingested_document",
                subject_id=str(doc.id),
                payload={"batch_id": batch.id, "file": f.name, "source": "onboarding"},
            )
        except Exception as e:
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name=f.name,
                status=OnboardingItemStatus.FAILED,
                error_message=str(e)[:500],
            )
            failed += 1

    batch.imported_count = imported
    batch.skipped_count = skipped
    batch.failed_count = failed
    batch.total_count = imported + skipped + failed
    batch.status = "completed" if failed == 0 else ("partial" if imported > 0 else "completed")
    batch.save()

    return batch
