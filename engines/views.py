"""Engines API - web chat endpoints for sales, support, recommendation.
All flows go through the canonical orchestration path (orchestration.service.run_canonical_pipeline).
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.request import Request

from orchestration.service import run_canonical_pipeline
from engines.demo_persistence import get_or_create_web_conversation
from engines.throttle import is_rate_limited
from engines.objection_library import detect_objection, get_objection_response
from engines.templates import TEMPLATES
from engines.lang_utils import detect_response_language
from engines.cta_mapping import to_customer_facing_next_step


def _throttle_check(request: Request) -> Response | None:
    """Return error response if rate limited."""
    if is_rate_limited(request):
        return Response(
            {"error": "Too many requests. Please wait a moment.", "rate_limited": True},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def sales_chat(request: Request) -> Response:
    """
    POST { "message": "...", "mode": "hot_lead", "qualification": {} }
    Returns: { response, mode } — reply text and selected mode.
    Uses canonical multi-agent pipeline (Intent → LeadQualification → Memory → ... → ResponseComposer).
    """
    if err := _throttle_check(request):
        return err
    data = request.data or {}
    msg = data.get("message", "")
    if not msg:
        return Response({"error": "message required"}, status=status.HTTP_400_BAD_REQUEST)
    mode = data.get("mode", "warm_lead")
    qual = data.get("qualification", {})
    try:
        resp, run, _user_msg, _assistant_msg = run_canonical_pipeline(
            request,
            msg,
            response_mode="sales",
            sales_mode=mode,
            qualification_override=qual if qual else None,
            use_llm=data.get("use_llm", True),
        )
        payload = {"response": resp, "mode": mode}
        if run:
            sc = run.scoring or {}
            rt = run.routing or {}
            rec_result = getattr(run, "recommendation_result", {}) or {}
            payload["temperature"] = sc.get("temperature", "")
            payload["score"] = sc.get("score")
            payload["recommendation_ready"] = rec_result.get("recommendation_ready", False)
            payload["matches"] = getattr(run, "recommendation_matches", []) or []
            raw_next = rt.get("recommended_cta") or sc.get("next_best_action", "") or rt.get("next_sales_move", "")
            ns_mapped = to_customer_facing_next_step(raw_next) if raw_next else None
            payload["next_step"] = ns_mapped if ns_mapped else ""
            payload["journey_stage"] = run.journey_stage or ""
            # Operator/debug panel: multi-agent visibility (never in customer message body)
            qual_out = run.qualification or {}
            intel = run.intent_result or {}
            mem = run.memory or {}
            payload["pipeline"] = {
                "intent": intel.get("primary") or intel.get("sales_intent"),
                "entities": intel.get("entities", {}),
                "memory_state": {
                    "customer_type": mem.get("customer_type_hint", ""),
                    "key_facts": (mem.get("key_facts") or [])[:5],
                },
                "lead_score": sc.get("score"),
                "lead_temperature": sc.get("temperature"),
                "buyer_stage": run.journey_stage,
                "recommendation_ready": rec_result.get("recommendation_ready", False),
                "recommendation_block_reason": rec_result.get("recommendation_block_reason", ""),
                "agents_executed": [
                    "intent", "lead_qualification", "memory", "retrieval",
                    "property_matching", "recommendation", "sales_strategy",
                    "persuasion", "journey_stage", "conversation_plan", "response_composer",
                ],
                "qualification": {
                    "budget": f"{qual_out.get('budget_min')}-{qual_out.get('budget_max')}" if (qual_out.get("budget_min") or qual_out.get("budget_max")) else None,
                    "location": qual_out.get("location_preference"),
                    "property_type": qual_out.get("property_type"),
                    "missing_fields": qual_out.get("missing_fields", []),
                },
            }
        return Response(payload)
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="engine", exc=e, stage="sales_chat")
        except ImportError:
            pass
        from django.conf import settings
        err = str(e) if settings.DEBUG else "An error occurred."
        return Response({"response": err, "error": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def support_chat(request: Request) -> Response:
    """
    POST { "message": "...", "category": "installment", "is_angry": false }
    Routes through canonical orchestration path.
    """
    if err := _throttle_check(request):
        return err
    data = request.data or {}
    msg = data.get("message", "")
    if not msg:
        return Response({"error": "message required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        resp, _run, _user_msg, _assistant_msg = run_canonical_pipeline(
            request,
            msg,
            response_mode="support",
            is_angry=data.get("is_angry", False),
            support_category=data.get("category", ""),
            use_llm=data.get("use_llm", True),
        )
        return Response({"response": resp})
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="engine", exc=e, stage="support_chat")
        except ImportError:
            pass
        from django.conf import settings
        err = str(e) if settings.DEBUG else "An error occurred."
        return Response({"response": err, "error": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def recommend(request: Request) -> Response:
    """
    POST {
      "budget_min": 1500000,
      "budget_max": 3000000,
      "location_preference": "New Cairo",
      "property_type": "apartment",
      "purpose": "residence",
      "urgency": "soon",
      "lang": "ar"
    }
    Routes through canonical orchestration path.
    """
    data = request.data or {}
    qual_override = {
        "budget_min": str(data.get("budget_min")) if data.get("budget_min") is not None else None,
        "budget_max": str(data.get("budget_max")) if data.get("budget_max") is not None else None,
        "location_preference": data.get("location_preference", ""),
        "property_type": data.get("property_type", ""),
        "purpose": data.get("purpose", ""),
        "urgency": data.get("urgency", ""),
    }
    if err := _throttle_check(request):
        return err
    content = f"Recommend: budget {data.get('budget_min')}-{data.get('budget_max')}, location {data.get('location_preference', '')}"
    try:
        resp, run, _user_msg, _assistant_msg = run_canonical_pipeline(
            request,
            content,
            response_mode="recommendation",
            qualification_override=qual_override,
            lang=data.get("lang", "ar"),
        )
        rec_result = getattr(run, "recommendation_result", {}) or {}
        payload = {
            "response": resp,
            "matches": run.recommendation_matches,
            "top_recommendations": rec_result.get("top_recommendations") or run.recommendation_matches,
            "why_it_matches": rec_result.get("why_it_matches", []),
            "tradeoffs": rec_result.get("tradeoffs", []),
            "recommendation_confidence": rec_result.get("recommendation_confidence") or rec_result.get("overall_confidence"),
            "overall_confidence": rec_result.get("overall_confidence"),
            "alternatives": rec_result.get("alternatives", []),
            "data_completeness": rec_result.get("data_completeness"),
        }
        return Response(payload)
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="engine", exc=e, stage="recommend")
        except ImportError:
            pass
        from django.conf import settings
        err = str(e) if settings.DEBUG else "An error occurred."
        return Response({"response": err, "matches": [], "error": err}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def project_detail(request: Request, project_id: int) -> Response:
    """
    GET /api/engines/project/<id>/
    Returns project details as JSON for chat demo "View details" modal.
    Public, read-only. Uses knowledge.Project.
    """
    if err := _throttle_check(request):
        return err
    try:
        from knowledge.models import Project
        from knowledge.services.structured_facts import get_project_structured_facts

        project = Project.objects.filter(pk=project_id, is_active=True).first()
        if not project:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        facts = get_project_structured_facts(project.id)
        payload = {
            "id": project.id,
            "name": project.name,
            "name_ar": project.name_ar or project.name,
            "location": project.location or "",
            "property_types": project.property_types or [],
            "price_min": float(project.price_min) if project.price_min else None,
            "price_max": float(project.price_max) if project.price_max else None,
            "availability_status": project.availability_status or "",
        }
        if facts:
            payload["pricing"] = facts.pricing.value if facts.pricing else None
            payload["payment_plan"] = facts.payment_plan.value if facts.payment_plan else None
            payload["delivery"] = facts.delivery.value if facts.delivery else None
            payload["unit_categories"] = getattr(facts, "unit_categories", []) or []
        return Response(payload)
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="engine", exc=e, stage="project_detail")
        except ImportError:
            pass
        from django.conf import settings
        return Response(
            {"error": str(e) if settings.DEBUG else "An error occurred."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def conversation_history(request: Request) -> Response:
    """
    GET returns messages for the current web session's conversation.
    Used for session continuity when the user reloads the page.
    Returns: { conversation_id, messages: [{ role, content }], has_session: bool }
    """
    if err := _throttle_check(request):
        return err
    try:
        customer, conversation = get_or_create_web_conversation(request)
    except Exception:
        return Response({
            "conversation_id": None,
            "messages": [],
            "has_session": False,
        })
    msgs = list(conversation.messages.order_by("created_at")[:50])
    messages = []
    for m in msgs:
        entry = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.metadata:
            meta = m.metadata or {}
            entry["temperature"] = meta.get("temperature")
            entry["matches"] = meta.get("matches", [])
            entry["next_step"] = meta.get("next_step")
            entry["recommendation_ready"] = bool(entry["matches"])
        messages.append(entry)
    return Response({
        "conversation_id": conversation.id,
        "messages": messages,
        "has_session": True,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def templates_list(request: Request) -> Response:
    """List available template modes."""
    return Response({
        "modes": list(TEMPLATES.keys()),
        "templates": {k: {"opening_ar": v.opening_ar, "opening_en": v.opening_en} for k, v in TEMPLATES.items()},
    })


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])  # No auth => no SessionAuthentication => no DRF CSRF enforcement
@permission_classes([AllowAny])
def objection_detect(request: Request) -> Response:
    """Detect objection from message."""
    msg = (request.data or {}).get("message", "")
    key = detect_objection(msg)
    if not key:
        return Response({"detected": False})
    lang = detect_response_language(msg)
    resp = get_objection_response(key, lang)
    return Response({"detected": True, "key": key, "response": resp})
