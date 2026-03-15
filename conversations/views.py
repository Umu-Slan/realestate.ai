"""
Conversation API endpoints.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from conversations.services import process_user_message


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    """
    Receive user message, return assistant response.
    Body: { "external_id": "...", "content": "...", "channel": "web", "phone": "", "email": "", "name": "" }
    """
    data = request.data
    external_id = data.get("external_id")
    content = data.get("content")

    if not external_id or not content:
        return Response(
            {"error": "external_id and content are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = process_user_message(
        external_id=external_id,
        content=content,
        channel=data.get("channel", "web"),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        name=data.get("name", ""),
    )
    return Response(result)
