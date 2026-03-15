"""Orchestration API - uses channel abstraction when channel provided."""
import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request

from orchestration.schemas import OrchestrationRun


def _json_safe(obj, default=str):
    """Convert non-JSON-serializable values for API response stability."""
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (Decimal, datetime, date)):
        return default(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v, default) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v, default) for v in obj]
    if isinstance(obj, set):
        return [_json_safe(v, default) for v in obj]
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return default(obj)


def _serialize_run(run: OrchestrationRun) -> dict:
    """Serialize OrchestrationRun to API response (JSON-safe)."""
    raw = {
        "run_id": run.run_id,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "current_stage": run.current_stage.value if hasattr(run.current_stage, "value") else str(run.current_stage),
        "intake": {
            "normalized_content": (run.intake.normalized_content or "")[:200] if run.intake else "",
            "validation_errors": run.intake.validation_errors if run.intake else [],
        } if run.intake else None,
        "intent": run.intent_result,
        "qualification": run.qualification,
        "scoring": run.scoring,
        "routing": run.routing,
        "retrieval_plan": run.retrieval_plan,
        "retrieval_sources": run.retrieval_sources,
        "policy_decision": run.policy_decision,
        "response": run.final_response,
        "actions_triggered": run.actions_triggered,
        "escalation_flags": run.escalation_flags,
        "handoff_summary": run.handoff_summary,
        "failure_reason": run.failure_reason,
    }
    return _json_safe(raw)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def orchestrate(request: Request) -> Response:
    """
    Run orchestration pipeline on incoming message.
    POST body: {
        "content": "user message",
        "channel": "web",
        "external_id": "user_123",
        "phone": "",
        "email": "",
        "conversation_id": 1,
        "conversation_history": [{"role": "user", "content": "..."}],
        "customer_id": 1,
        "use_llm": true
    }
    """
    data = request.data or {}
    channel = data.get("channel", "web")
    content = data.get("content", "")
    if not content:
        return Response(
            {"error": "content is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from channels.service import process_inbound_message
        _, run = process_inbound_message(channel, data)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="orchestration_api", exc=e, stage="process_inbound_message")
        except ImportError:
            pass
        logger.exception("Orchestration failed: %s", e)
        return Response(
            {"error": "Orchestration failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(_serialize_run(run))
