"""
Conversation orchestration. Entry point for incoming messages.
"""
from leads.models import Customer, CustomerIdentity
from conversations.models import Conversation, Message
from core.adapters.llm import get_llm_client
from core.enums import SourceChannel, ConversationStatus
from audit.service import log


def resolve_or_create_identity(external_id: str, phone: str = "", email: str = "", name: str = "") -> CustomerIdentity:
    """Resolve identity for new vs existing customer detection."""
    identity, _ = CustomerIdentity.objects.get_or_create(
        external_id=external_id,
        defaults={"phone": phone, "email": email, "name": name},
    )
    return identity


def get_or_create_customer(identity: CustomerIdentity, channel: str = "web", company=None) -> Customer:
    """Get or create customer for identity."""
    from companies.services import get_default_company
    company = company or get_default_company()
    customer = Customer.objects.filter(identity=identity, is_active=True, company=company).first()
    if not customer:
        ch = channel if channel in [c[0] for c in SourceChannel.choices] else SourceChannel.WEB
        customer = Customer.objects.create(identity=identity, source_channel=ch, company=company)
    return customer


def get_or_create_conversation(customer: Customer) -> Conversation:
    """Get active conversation or create new one."""
    from companies.services import get_default_company
    conv = customer.conversations.filter(status=ConversationStatus.ACTIVE).first()
    if not conv:
        conv = Conversation.objects.create(
            customer=customer,
            company=customer.company or get_default_company(),
        )
    return conv


def process_user_message(
    external_id: str,
    content: str,
    channel: str = "web",
    phone: str = "",
    email: str = "",
    name: str = "",
) -> dict:
    """
    Main entry: process incoming user message, return assistant response.
    v0: simplified flow — identity, conversation, generate, audit.
    """
    identity = resolve_or_create_identity(external_id, phone, email, name)
    customer = get_or_create_customer(identity, channel)
    conversation = get_or_create_conversation(customer)

    # Save user message
    user_msg = Message.objects.create(
        conversation=conversation,
        role="user",
        content=content,
    )

    # Build context from prior messages
    prior = list(conversation.messages.filter(role__in=["user", "assistant"]).order_by("created_at")[:10])
    messages = [{"role": m.role, "content": m.content} for m in prior]
    # Append current user message
    messages.append({"role": "user", "content": content})

    # Generate response (generation module will add system prompt, retrieval, etc)
    client = get_llm_client()
    response_text = client.chat_completion(messages)

    # Save assistant message
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=response_text,
    )

    log(
        action="message_processed",
        actor=external_id,
        subject_type="conversation",
        subject_id=conversation.id,
        payload={"user_msg_id": user_msg.id, "assistant_msg_id": assistant_msg.id},
    )

    return {
        "response": response_text,
        "conversation_id": conversation.id,
        "message_id": assistant_msg.id,
    }
