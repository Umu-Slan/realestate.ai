"""
CRM API: import, import summary, inbound events from external CRM.
"""
import tempfile
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from crm.models import CRMImportBatch
from crm.services.import_service import import_crm_file
from crm.services.external_sync import upsert_crm_lead_from_payload


def _crm_inbound_authorized(request) -> bool:
    secret = (getattr(settings, "CRM_INBOUND_WEBHOOK_SECRET", None) or "").strip()
    if not secret:
        return bool(getattr(settings, "DEBUG", False))
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        if auth[7:].strip() == secret:
            return True
    if (request.headers.get("X-Webhook-Secret") or "").strip() == secret:
        return True
    return False


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


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def crm_events_inbound(request):
    """
    Receive lead updates from the company's CRM / middleware.

    POST /api/crm/events/
    Auth: set CRM_INBOUND_WEBHOOK_SECRET in .env, then send:
      Authorization: Bearer <secret>   OR   X-Webhook-Secret: <secret>
    If secret is unset, only DEBUG=True accepts requests (unsafe for production).

    Body JSON: crm_id (required), name, phone, email, notes, lead_stage, owner, tags, ...
    """
    if not _crm_inbound_authorized(request):
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data if isinstance(request.data, dict) else {}
    result = upsert_crm_lead_from_payload(data, actor="crm_inbound_webhook")
    st = result.get("status", "error")
    if st == "error":
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)
