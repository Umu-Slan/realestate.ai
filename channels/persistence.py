"""
Channel persistence: Customer and Conversation lookup/creation.
Unified for web and WhatsApp - same orchestration path.
- WhatsApp: phone-based identity
- Web: external_id/session-based identity
"""
from typing import Optional, TYPE_CHECKING

from django.db import transaction

from leads.models import Customer, CustomerIdentity
from core.enums import CustomerType, SourceChannel
from conversations.models import Conversation

if TYPE_CHECKING:
    from channels.schema import NormalizedInboundMessage


def get_or_create_customer_conversation(
    normalized_msg: "NormalizedInboundMessage",
) -> tuple[Customer, Conversation]:
    """
    Get or create Customer and Conversation for any channel.
    Dispatches to channel-specific logic. Same schema for web and WhatsApp.
    """
    channel = (normalized_msg.source_channel or "web").lower()
    if channel == "whatsapp":
        return get_or_create_whatsapp_customer_conversation(
            phone=normalized_msg.phone,
            external_id=normalized_msg.external_id or None,
            contact_name=normalized_msg.name,
        )
    return get_or_create_web_customer_conversation_from_normalized(normalized_msg)


def get_or_create_web_customer_conversation_from_normalized(
    normalized_msg: "NormalizedInboundMessage",
) -> tuple[Customer, Conversation]:
    """
    Get or create Customer and Conversation for web/demo channel.
    Uses external_id, conversation_id, or customer_id from normalized message.
    """
    channel = SourceChannel.WEB
    conv_id = normalized_msg.conversation_id
    cust_id = normalized_msg.customer_id
    external_id = (normalized_msg.external_id or "").strip()
    if not external_id:
        external_id = f"web:anon"
    if not external_id.startswith("web:"):
        external_id = f"web:{external_id}"

    from companies.services import get_default_company
    from companies.models import Company

    company = get_default_company() or (Company.objects.first() if Company.objects.exists() else None)
    if not company:
        raise ValueError("No company available for web conversation")

    with transaction.atomic():
        if conv_id:
            conv = Conversation.objects.filter(
                pk=conv_id,
                channel=channel,
            ).select_related("customer", "customer__identity").first()
            if conv:
                return conv.customer, conv
        if cust_id:
            cust = Customer.objects.filter(pk=cust_id).select_related("identity").first()
            if cust:
                conv = (
                    Conversation.objects.filter(customer=cust, channel=channel)
                    .order_by("-created_at")
                    .first()
                )
                if not conv:
                    conv = Conversation.objects.create(
                        customer=cust,
                        company=company,
                        channel=channel,
                        metadata={"source": "web_chat"},
                    )
                return cust, conv

        identity, _ = CustomerIdentity.objects.get_or_create(
            external_id=external_id,
            defaults={
                "name": normalized_msg.name or "Web Visitor",
                "phone": normalized_msg.phone or "",
                "email": normalized_msg.email or "",
                "metadata": {"source": "web_chat", "channel": "web"},
            },
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
        conversation = (
            Conversation.objects.filter(customer=customer, channel=channel)
            .order_by("-created_at")
            .first()
        )
        if not conversation:
            conversation = Conversation.objects.create(
                customer=customer,
                company=company,
                channel=channel,
                metadata={"source": "web_chat"},
            )
    return customer, conversation


def get_or_create_whatsapp_customer_conversation(
    phone: str,
    *,
    external_id: Optional[str] = None,
    company_id: Optional[int] = None,
    contact_name: str = "",
) -> tuple[Customer, Conversation]:
    """
    Get or create Customer and Conversation for WhatsApp by phone.
    Identity: whatsapp:{normalized_phone}. One active conversation per customer.
    Returns (customer, conversation).
    """
    phone = (phone or "").strip()
    if not phone:
        raise ValueError("phone is required for WhatsApp customer lookup")
    # Normalize for identity key
    digits = "".join(c for c in phone if c.isdigit())
    if digits and not digits.startswith("20"):
        digits = "20" + digits.lstrip("0")
    ext_id = external_id or f"whatsapp:{digits or phone}"

    from companies.services import get_default_company
    from companies.models import Company

    company = None
    if company_id:
        company = Company.objects.filter(pk=company_id).first()
    if not company:
        company = get_default_company()
    if not company:
        raise ValueError("No company available for WhatsApp conversation")

    with transaction.atomic():
        identity, _ = CustomerIdentity.objects.get_or_create(
            external_id=ext_id,
            defaults={
                "name": contact_name or f"WhatsApp {phone[:6]}***",
                "phone": phone,
                "metadata": {"source": "whatsapp", "channel": "whatsapp"},
            },
        )
        if contact_name and (not identity.name or identity.name.startswith("WhatsApp ")):
            identity.name = contact_name
            identity.save(update_fields=["name"])

        customer, _ = Customer.objects.get_or_create(
            identity=identity,
            defaults={
                "customer_type": CustomerType.NEW_LEAD,
                "source_channel": SourceChannel.WHATSAPP,
                "company": company,
                "metadata": {"whatsapp": True, "phone": phone},
            },
        )

        conversation = (
            Conversation.objects.filter(
                customer=customer,
                channel=SourceChannel.WHATSAPP,
            )
            .order_by("-created_at")
            .first()
        )
        if not conversation:
            conversation = Conversation.objects.create(
                customer=customer,
                company=company,
                channel=SourceChannel.WHATSAPP,
                metadata={"source": "whatsapp", "phone": phone},
            )
    return customer, conversation
