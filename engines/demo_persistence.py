"""
Web chat persistence: create Customer, Conversation, Messages for website chat.
Uses Django session for browser session continuity. Production-ready: WEB channel.
"""
from django.db import transaction

from leads.models import Customer, CustomerIdentity
from core.enums import CustomerType
from conversations.models import Conversation, Message
from core.enums import SourceChannel


def _get_web_session_id(request) -> str:
    """Unique id for web chat customer per browser session."""
    session = getattr(request, "session", None)
    if not session:
        return "web:anonymous"
    session_key = session.session_key or ""
    if not session_key:
        session.create()
        session_key = session.session_key or ""
    return f"web:{session_key}" if session_key else "web:anonymous"


@transaction.atomic
def get_or_create_web_conversation(
    request,
    channel: str = SourceChannel.WEB,
) -> tuple[Customer, Conversation]:
    """
    Get or create web chat customer and conversation for this browser session.
    Uses WEB channel so operators can filter web-origin conversations.
    Returns (customer, conversation).
    """
    external_id = _get_web_session_id(request)
    session = getattr(request, "session", None)
    session_key = "web_conversation_id"

    if session:
        conv_id = session.get(session_key)
        if conv_id:
            conv = Conversation.objects.filter(
                pk=conv_id, customer__identity__external_id=external_id
            ).select_related("customer", "customer__identity").first()
            if conv:
                return conv.customer, conv

    from companies.services import get_default_company
    company = get_default_company()
    identity, _ = CustomerIdentity.objects.get_or_create(
        external_id=external_id,
        defaults={"name": "Web Visitor", "metadata": {"source": "web_chat"}},
    )
    customer, _ = Customer.objects.get_or_create(
        identity=identity,
        defaults={
            "customer_type": CustomerType.NEW_LEAD,
            "source_channel": channel,
            "company": company,
            "metadata": {"web_chat": True},
        },
    )
    conversation = Conversation.objects.create(
        customer=customer,
        company=customer.company or company,
        channel=channel,
        metadata={"source": "web_chat"},
    )
    if session:
        session[session_key] = conversation.id
        session.modified = True
    return customer, conversation


def get_or_create_demo_conversation(request) -> tuple[Customer, Conversation]:
    """Backward-compat: alias for get_or_create_web_conversation with WEB channel."""
    return get_or_create_web_conversation(request, channel=SourceChannel.WEB)


def persist_demo_message(
    request,
    user_content: str,
    assistant_content: str,
    mode: str,
    extra_metadata: dict | None = None,
) -> Message | None:
    """
    Persist a user message and assistant reply to the demo conversation.
    Returns the assistant Message, or None if persistence was skipped.
    """
    try:
        customer, conversation = get_or_create_demo_conversation(request)
    except Exception:
        return None

    user_msg = Message.objects.create(
        conversation=conversation,
        role="user",
        content=user_content,
        metadata={"mode": mode, **(extra_metadata or {})},
    )
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=assistant_content,
        metadata={"mode": mode, **(extra_metadata or {})},
    )
    return assistant_msg
