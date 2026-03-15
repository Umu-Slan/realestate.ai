"""Channel webhook views. WhatsApp production-ready."""
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _verify_whatsapp_token(token: str) -> bool:
    """Verify hub.verify_token against settings."""
    expected = getattr(settings, "WHATSAPP_VERIFY_TOKEN", None)
    if not expected:
        return bool(token)
    return token == expected


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    """
    WhatsApp Business API webhook.
    GET: Meta verification (hub.mode=subscribe, hub.verify_token, hub.challenge)
    POST: Inbound messages -> normalize -> canonical pipeline -> outbound
    Returns 200 on success; 200 with status on non-message payloads (status updates).
    """
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token and challenge and _verify_whatsapp_token(token):
            return Response(challenge, status=status.HTTP_200_OK)
        logger.warning("WhatsApp verification failed: mode=%s token_present=%s", mode, bool(token))
        return Response({"error": "Verification failed"}, status=status.HTTP_403_FORBIDDEN)

    data = request.data or {}
    if "entry" not in data:
        return Response({"status": "ok", "message": "No entry in payload"}, status=status.HTTP_200_OK)

    # Skip status updates (read, delivered) - no messages to process
    has_messages = False
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "messages" and change.get("value", {}).get("messages"):
                has_messages = True
                break
        if has_messages:
            break
    if not has_messages:
        return Response({"status": "ok", "message": "Status update or no messages"}, status=status.HTTP_200_OK)

    try:
        from channels.service import process_inbound_message
        msg, run = process_inbound_message("whatsapp", data)
        response_preview = (run.final_response or "")[:500] if hasattr(run, "final_response") else ""
        return Response({
            "status": "processed",
            "run_id": getattr(run, "run_id", ""),
            "response_preview": response_preview,
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        logger.warning("WhatsApp webhook validation error: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("WhatsApp webhook processing failed: %s", e)
        return Response(
            {"error": "Processing failed", "detail": str(e) if settings.DEBUG else ""},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
