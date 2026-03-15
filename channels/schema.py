"""
Normalized inbound message schema.
Single internal representation regardless of source channel.
All adapters (web, whatsapp, demo) produce this canonical shape.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


# Canonical fields required for orchestration - same regardless of channel
CANONICAL_ORCHESTRATION_FIELDS = (
    "raw_content", "channel", "external_id", "phone", "email", "name",
    "conversation_id", "customer_id", "conversation_history", "use_llm",
    "response_mode", "sales_mode", "is_angry", "support_category",
    "qualification_override", "lang",
)


@dataclass
class NormalizedInboundMessage:
    """
    Canonical inbound message. All channel adapters produce this.
    Preserves channel metadata for audit: phone, external_message_id, timestamp.
    """

    content: str
    source_channel: str
    external_id: str = ""
    phone: str = ""
    email: str = ""
    name: str = ""
    timestamp: Optional[datetime] = None
    campaign: str = ""
    source: str = ""
    conversation_id: Optional[int] = None
    customer_id: Optional[int] = None
    external_message_id: str = ""  # Provider message ID for idempotency/audit
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            from django.utils import timezone
            self.timestamp = timezone.now()
        # Channel metadata for Message persistence and audit
        self.metadata.setdefault("phone", self.phone)
        self.metadata.setdefault("external_message_id", self.external_message_id)
        self.metadata.setdefault("source_channel", self.source_channel)
        if self.timestamp:
            self.metadata.setdefault("message_timestamp", self.timestamp.isoformat())

    def to_orchestration_params(self) -> dict:
        """Map to run_orchestration kwargs. Single schema for all channels."""
        extra = self.metadata or {}
        return {
            "raw_content": self.content,
            "channel": self.source_channel,
            "external_id": self.external_id or "anonymous",
            "phone": self.phone,
            "email": self.email,
            "name": self.name,
            "conversation_id": self.conversation_id,
            "customer_id": self.customer_id,
            "conversation_history": extra.get("conversation_history"),
            "use_llm": extra.get("use_llm", True),
            "response_mode": extra.get("response_mode"),
            "sales_mode": extra.get("sales_mode", "warm_lead"),
            "is_angry": extra.get("is_angry", False),
            "support_category": extra.get("support_category", ""),
            "qualification_override": extra.get("qualification_override"),
            "lang": extra.get("lang", "ar"),
        }

    def to_channel_metadata(self) -> dict:
        """Channel-specific metadata to preserve in Message.metadata."""
        meta = dict(self.metadata or {})
        meta["source_channel"] = self.source_channel
        if self.phone:
            meta["phone"] = self.phone
        if self.external_message_id:
            meta["external_message_id"] = self.external_message_id
        if self.timestamp:
            meta["message_timestamp"] = self.timestamp.isoformat()
        return meta
