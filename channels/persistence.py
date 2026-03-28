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


def _external_id_for_connector(connector: str, external_id: str) -> str:
    """Stable unique key per channel (telegram:123, web:session, …)."""
    ext = (external_id or "").strip()
    if not ext:
        ext = "anon"
    c = (connector or "web").lower()
    if ":" in ext:
        if ext.startswith(f"{c}:") or (c in ("web", "demo") and ext.startswith("web:")):
            return ext
        if not ext.startswith("web:"):
            return ext
    if c in ("web", "demo"):
        if ext.startswith("web:"):
            return ext
        return f"web:{ext}"
    return f"{c}:{ext}"


def _conversation_db_channel(connector: str) -> tuple[str, dict]:
    """Map connector string to Conversation.channel + extra metadata."""
    c = (connector or "web").lower()
    if c == "demo":
        return SourceChannel.DEMO, {}
    if c == "web":
        return SourceChannel.WEB, {}
    if c == "instagram":
        return SourceChannel.INSTAGRAM, {}
    if c == "email":
        return SourceChannel.EMAIL, {}
    if c == "phone":
        return SourceChannel.PHONE, {}
    return SourceChannel.API, {"connector": c}


def _find_conversation_for_customer(customer: Customer, db_channel: str, connector: str):
    qs = Conversation.objects.filter(customer=customer, channel=db_channel)
    if db_channel == SourceChannel.API:
        qs = qs.filter(metadata__connector=connector)
    return qs.order_by("-created_at").first()


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
    Get or create Customer and Conversation for any JSON-backed connector
    (web, demo, Telegram, Meta, SMS gateway, etc.). WhatsApp uses a separate path.
    """
    connector = (normalized_msg.source_channel or "web").lower()
    db_channel, _ch_meta = _conversation_db_channel(connector)
    ext_key = _external_id_for_connector(connector, normalized_msg.external_id)
    conv_id = normalized_msg.conversation_id
    cust_id = normalized_msg.customer_id

    from companies.services import get_default_company
    from companies.models import Company

    company = get_default_company() or (Company.objects.first() if Company.objects.exists() else None)
    if not company:
        raise ValueError("No company available for conversation")

    with transaction.atomic():
        if conv_id:
            conv = Conversation.objects.filter(pk=conv_id).select_related(
                "customer", "customer__identity"
            ).first()
            if conv:
                return conv.customer, conv
        if cust_id:
            cust = Customer.objects.filter(pk=cust_id).select_related("identity").first()
            if cust:
                conv = _find_conversation_for_customer(cust, db_channel, connector)
                if not conv:
                    meta = {"source": "omnichannel", "connector": connector}
                    conv = Conversation.objects.create(
                        customer=cust,
                        company=company,
                        channel=db_channel,
                        metadata=meta,
                    )
                return cust, conv

        identity, created = CustomerIdentity.objects.get_or_create(
            external_id=ext_key,
            defaults={
                "name": normalized_msg.name or "Visitor",
                "phone": normalized_msg.phone or "",
                "email": normalized_msg.email or "",
                "metadata": {"source": "omnichannel", "connector": connector},
            },
        )
        if not created:
            upd = []
            if normalized_msg.name and (not identity.name or identity.name == "Visitor"):
                identity.name = normalized_msg.name
                upd.append("name")
            if normalized_msg.phone and not identity.phone:
                identity.phone = normalized_msg.phone
                upd.append("phone")
            if normalized_msg.email and not identity.email:
                identity.email = normalized_msg.email
                upd.append("email")
            if upd:
                identity.save(update_fields=upd + ["updated_at"])

        customer, _ = Customer.objects.get_or_create(
            identity=identity,
            defaults={
                "customer_type": CustomerType.NEW_LEAD,
                "source_channel": db_channel,
                "company": company,
                "metadata": {"connector": connector, "omnichannel": True},
            },
        )
        conversation = _find_conversation_for_customer(customer, db_channel, connector)
        if not conversation:
            conversation = Conversation.objects.create(
                customer=customer,
                company=company,
                channel=db_channel,
                metadata={"source": "omnichannel", "connector": connector},
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
