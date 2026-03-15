"""
Outbound provider interface - abstract contract for sending messages.
Implementations: WhatsApp Cloud API, Twilio, etc.
Adapter layer only - no business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OutboundResult:
    """Result of outbound send attempt."""
    success: bool
    external_id: Optional[str] = None  # Provider message ID
    error: Optional[str] = None


class BaseOutboundProvider(ABC):
    """Interface for sending messages to a channel."""

    channel_name: str = "base"

    @abstractmethod
    def send_text(
        self,
        to_phone: str,
        text: str,
        *,
        reply_to_message_id: Optional[str] = None,
    ) -> OutboundResult:
        """
        Send text message. Returns OutboundResult.
        to_phone: E.164 or normalized phone.
        """
        raise NotImplementedError
