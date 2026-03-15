"""
Base channel adapter interface.
Each channel (web, whatsapp, etc.) implements normalize(raw_payload) -> NormalizedInboundMessage.
"""
from abc import ABC, abstractmethod
from typing import Any

from channels.schema import NormalizedInboundMessage


class BaseChannelAdapter(ABC):
    """Interface for inbound channel adapters."""

    channel_name: str = "base"

    @abstractmethod
    def normalize(self, raw_payload: dict[str, Any]) -> NormalizedInboundMessage:
        """
        Convert channel-specific payload to NormalizedInboundMessage.
        Raises ValueError if payload is invalid.
        """
        raise NotImplementedError

    def validate(self, raw_payload: dict[str, Any]) -> tuple[bool, str]:
        """Return (is_valid, error_message). Override for stricter validation."""
        if not raw_payload:
            return False, "Empty payload"
        return True, ""
