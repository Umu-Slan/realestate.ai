"""
Intelligence API views.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request

from intelligence.services.pipeline import analyze_message
from intelligence.serializers import serialize_intelligence


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def classify_and_score(request: Request) -> Response:
    """
    Run classification and scoring on a message.
    POST body: {
        "message_text": "...",
        "conversation_history": [{"role": "user", "content": "..."}, ...],
        "customer_id": 1,
        "customer_type": "new_lead",
        "is_existing_customer": false,
        "is_returning_lead": false,
        "message_count": 1,
        "has_project_match": false,
        "is_angry": false,
        "exact_price_available": true,
        "use_llm": true
    }
    """
    data = request.data or {}
    message_text = data.get("message_text", "")
    if not message_text:
        return Response(
            {"error": "message_text is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = analyze_message(
        message_text,
        conversation_history=data.get("conversation_history"),
        customer_id=data.get("customer_id"),
        customer_type=data.get("customer_type", ""),
        is_existing_customer=data.get("is_existing_customer", False),
        is_returning_lead=data.get("is_returning_lead", False),
        message_count=data.get("message_count", 1),
        has_project_match=data.get("has_project_match", False),
        decision_authority_signals=data.get("decision_authority_signals", False),
        is_angry=data.get("is_angry", False),
        exact_price_available=data.get("exact_price_available", True),
        use_llm=data.get("use_llm", True),
    )

    return Response(serialize_intelligence(result))
