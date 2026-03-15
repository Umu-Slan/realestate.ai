"""
CRM API: import, import summary.
"""
import tempfile
from pathlib import Path

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from crm.models import CRMImportBatch
from crm.services.import_service import import_crm_file


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_crm(request):
    """
    Import CRM file.
    Body: { "path": "/abs/path/to/file.csv" } or multipart file upload
    """
    path = request.data.get("path")
    if not path:
        f = request.FILES.get("file")
        if f:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(f.name).suffix) as tmp:
                for chunk in f.chunks():
                    tmp.write(chunk)
                path = tmp.name
        else:
            return Response({"error": "path or file required"}, status=status.HTTP_400_BAD_REQUEST)

    dry_run = request.data.get("dry_run", False)
    try:
        stats = import_crm_file(
            str(path),
            actor=str(request.user),
            dry_run=dry_run,
        )
        return Response(stats)
    except FileNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def import_summary(request):
    """List import batches with summary."""
    batches = CRMImportBatch.objects.all().order_by("-created_at")[:20]
    data = [
        {
            "batch_id": b.batch_id,
            "file_name": b.file_name,
            "total_rows": b.total_rows,
            "imported_count": b.imported_count,
            "duplicate_count": b.duplicate_count,
            "conflict_count": b.conflict_count,
            "error_count": b.error_count,
            "status": b.status,
            "created_at": b.created_at.isoformat(),
        }
        for b in batches
    ]
    return Response(data)
