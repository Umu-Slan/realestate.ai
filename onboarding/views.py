"""
Onboarding console views: upload documents, structured data, CRM; inspect batches.
"""
import uuid
from pathlib import Path

from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType
from onboarding.services import run_document_batch, import_structured_csv
from knowledge.models import IngestedDocument, Project
from companies.models import Company
from core.enums import DocumentType
from crm.services.import_service import import_crm_file


def _default_company():
    """Get default company for onboarding (first active)."""
    return Company.objects.filter(is_active=True).first()


@require_http_methods(["GET"])
def onboarding_dashboard(request):
    """Main onboarding dashboard: upload forms, recent batches."""
    company = _default_company()
    batches = OnboardingBatch.objects.all().order_by("-created_at")[:20]
    document_types = DocumentType.choices
    projects = Project.objects.filter(is_active=True).order_by("name")[:100]
    return render(request, "onboarding/dashboard.html", {
        "company": company,
        "batches": batches,
        "document_types": document_types,
        "projects": projects,
        "nav_section": "onboarding",
    })


@require_POST
def upload_documents(request):
    """Upload and ingest documents."""
    files = request.FILES.getlist("files")
    if not files:
        return redirect("onboarding:dashboard")
    doc_type = request.POST.get("document_type", "project_pdf")
    project_id = request.POST.get("project_id") or None
    if project_id:
        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            project_id = None
    company = _default_company()
    company_id = company.id if company else None
    source_of_truth = request.POST.get("source_of_truth") == "on"
    created_by = str(request.user) if request.user.is_authenticated else "operator"

    try:
        doc_type_enum = DocumentType(doc_type)
    except ValueError:
        doc_type_enum = DocumentType.PROJECT_PDF

    batch = run_document_batch(
        files=files,
        document_type=doc_type_enum,
        company_id=company_id,
        project_id=project_id,
        source_of_truth=source_of_truth,
        created_by=created_by,
    )
    return redirect("onboarding:batch_detail", pk=batch.id)


@require_POST
def upload_structured(request):
    """Upload and import structured project CSV."""
    f = request.FILES.get("file")
    if not f or not f.name.lower().endswith((".csv", ".xlsx", ".xls")):
        return redirect("onboarding:dashboard")

    upload_dir = Path(settings.MEDIA_ROOT) / "onboarding" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(f.name).suffix
    saved_path = upload_dir / ("structured_%s%s" % (uuid.uuid4().hex[:12], ext))
    with open(saved_path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)

    company = _default_company()
    created_by = str(request.user) if request.user.is_authenticated else "operator"

    if ext.lower() == ".csv":
        batch = import_structured_csv(
            file_path=str(saved_path),
            company_id=company.id if company else None,
            created_by=created_by,
        )
    else:
        # Excel not yet supported for structured; create failed batch
        from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType, OnboardingItemStatus
        batch = OnboardingBatch.objects.create(
            company=company,
            batch_type=OnboardingBatchType.STRUCTURED,
            status="completed",
            failed_count=1,
            total_count=1,
            created_by=created_by,
        )
        OnboardingItem.objects.create(
            batch=batch,
            item_type="structured_row",
            source_name=f.name,
            status=OnboardingItemStatus.FAILED,
            error_message="Excel import for structured data not yet implemented. Use CSV.",
        )

    return redirect("onboarding:batch_detail", pk=batch.id)


@require_POST
def upload_crm(request):
    """Upload and import CRM export."""
    f = request.FILES.get("file")
    if not f:
        return redirect("onboarding:dashboard")

    upload_dir = Path(settings.MEDIA_ROOT) / "onboarding" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(f.name).suffix
    saved_path = upload_dir / ("crm_%s%s" % (uuid.uuid4().hex[:12], ext))
    with open(saved_path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)

    created_by = str(request.user) if request.user.is_authenticated else "operator"
    result = import_crm_file(str(saved_path), dry_run=False, actor=created_by)

    # Create OnboardingBatch from CRM result for consistency
    from crm.models import CRMImportBatch
    crm_batch = CRMImportBatch.objects.filter(batch_id=result["batch_id"]).first()
    batch = OnboardingBatch.objects.create(
        company=_default_company(),
        batch_type=OnboardingBatchType.CRM,
        status=result.get("status", "completed"),
        imported_count=result.get("imported", 0),
        skipped_count=result.get("duplicates", 0) + result.get("conflicts", 0),
        failed_count=result.get("errors", 0),
        total_count=result.get("total_rows", 0),
        metadata={"crm_batch_id": result.get("batch_id"), "file_name": f.name},
        created_by=created_by,
    )

    return redirect("onboarding:batch_detail", pk=batch.id)


@require_http_methods(["GET"])
def batch_detail(request, pk):
    """Inspect a single onboarding batch and its items."""
    batch = get_object_or_404(OnboardingBatch, pk=pk)
    items = batch.items.all()[:100]
    return render(request, "onboarding/batch_detail.html", {
        "batch": batch,
        "items": items,
        "nav_section": "onboarding",
    })


@require_POST
def reindex_documents(request):
    """Reindex documents. POST body: document_ids (optional) or all."""
    from knowledge.embedding import embed_chunks

    ids = request.POST.getlist("document_ids") or request.GET.getlist("document_ids")
    docs = IngestedDocument.objects.filter(status__in=["parsed", "chunked", "embedded"])
    if ids:
        try:
            ids = [int(x) for x in ids]
            docs = docs.filter(id__in=ids)
        except (ValueError, TypeError):
            pass
    count = 0
    for doc in docs[:50]:  # limit
        chunks = list(doc.chunks.all())
        if chunks:
            embed_chunks(chunks)
            doc.status = "embedded"
            doc.save(update_fields=["status", "updated_at"])
            count += len(chunks)
    return redirect("onboarding:dashboard")
