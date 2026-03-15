"""
WhatsApp outbound provider - stub for Meta Cloud API.
When wired: use access token, phone_number_id, send via messages endpoint.
Ready for live integration.
"""
import logging
from typing import Optional

from .base import BaseOutboundProvider, OutboundResult

logger = logging.getLogger(__name__)

# Max WhatsApp text length (single message)
MAX_TEXT_LENGTH = 4096


def format_outbound_text(text: str) -> str:
    """Format reply for WhatsApp. Truncate if needed."""
    if not text:
        return ""
    text = str(text).strip()
    if len(text) > MAX_TEXT_LENGTH:
        text = text[: MAX_TEXT_LENGTH - 20] + "\n...[truncated]"
    return text


class WhatsAppStubProvider(BaseOutboundProvider):
    """
    Stub provider - logs outbound, does not send.
    Wire live: replace with HttpClient to Meta API.
    """

    channel_name = "whatsapp"

    def send_text(
        self,
        to_phone: str,
        text: str,
        *,
        reply_to_message_id: Optional[str] = None,
    ) -> OutboundResult:
        """Log only. Wire live provider for actual send."""
        text = format_outbound_text(text)
        logger.info(
            "whatsapp_outbound_stub: to=%s len=%d reply_to=%s",
            to_phone,
            len(text),
            reply_to_message_id or "-",
        )
        return OutboundResult(success=True, external_id=f"stub_{id(text)}")
