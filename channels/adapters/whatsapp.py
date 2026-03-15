"""
WhatsApp channel adapter - production-ready normalization for WhatsApp Business API.
Supports webhook payload shape and direct/test shape.
Preserves: phone, external_message_id, message_timestamp, source_channel.
"""
from typing import Any

from channels.schema import NormalizedInboundMessage
from .base import BaseChannelAdapter


def _normalize_phone(phone: str) -> str:
    """Normalize phone to digits-only for consistent identity. E.164 prefix preserved in display."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits and not digits.startswith("20"):
        digits = "20" + digits.lstrip("0")  # Egypt default
    return digits or phone


class WhatsAppChannelAdapter(BaseChannelAdapter):
    """
    WhatsApp Business API adapter.
    Parses webhook payload: entry -> changes -> value -> messages.
    Preserves channel metadata for audit and idempotency.
    See: https://developers.facebook.com/docs/whatsapp/cloud-api/webhook-components
    """

    channel_name = "whatsapp"

    def normalize(self, raw_payload: dict[str, Any]) -> NormalizedInboundMessage:
        """
        Normalize WhatsApp payload. Supports:
        - Direct/test: {"content": "...", "phone": "+20..."}
        - Webhook: entry[].changes[].value.messages[].text.body
        """
        if "content" in raw_payload:
            return self._normalize_direct(raw_payload)
        return self._normalize_webhook(raw_payload)

    def _normalize_direct(self, payload: dict) -> NormalizedInboundMessage:
        """Direct/test payload shape."""
        content = str(payload.get("content", "")).strip()
        phone = _normalize_phone(str(payload.get("phone", "")).strip())
        ext_id = str(payload.get("external_id", "")).strip() or (f"whatsapp:{phone}" if phone else "unknown")
        ext_msg_id = str(payload.get("external_message_id", "")).strip()
        meta = dict(payload.get("metadata", {}))
        meta["phone"] = phone or meta.get("phone", "")
        meta["external_message_id"] = ext_msg_id or meta.get("external_message_id", "")
        meta["source_channel"] = "whatsapp"
        return NormalizedInboundMessage(
            content=content or " ",
            source_channel="whatsapp",
            external_id=ext_id,
            phone=phone,
            email=str(payload.get("email", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            external_message_id=ext_msg_id,
            metadata=meta,
        )

    def _normalize_webhook(self, payload: dict) -> NormalizedInboundMessage:
        """WhatsApp Cloud API webhook shape."""
        content, phone, ext_msg_id, ts, name = self._parse_webhook_payload(payload)
        if not phone and not ext_msg_id:
            raise ValueError("WhatsApp webhook: no message (phone or id) in payload; may be status update")
        timestamp = None
        if ts is not None:
            try:
                from datetime import datetime
                timestamp = datetime.fromtimestamp(int(ts))
            except (ValueError, TypeError):
                pass
        phone_norm = _normalize_phone(phone) if phone else ""
        external_id = f"whatsapp:{phone_norm}" if phone_norm else (ext_msg_id or "unknown")
        meta = {
            "phone": phone or "",
            "external_message_id": ext_msg_id or "",
            "source_channel": "whatsapp",
        }
        if timestamp:
            meta["message_timestamp"] = timestamp.isoformat()
        meta["wa_contact_name"] = name
        return NormalizedInboundMessage(
            content=content or " ",
            source_channel="whatsapp",
            external_id=external_id,
            phone=phone or "",
            name=name,
            timestamp=timestamp,
            external_message_id=ext_msg_id or "",
            metadata=meta,
        )

    def _parse_webhook_payload(self, payload: dict) -> tuple[str, str, str, Any, str]:
        """Extract content, phone, external_message_id, timestamp, name from webhook."""
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") != "messages":
                        continue
                    val = change.get("value", {})
                    msgs = val.get("messages", [])
                    contacts = val.get("contacts", [])
                    name = ""
                    if contacts:
                        name = (contacts[0].get("profile") or {}).get("name", "") or ""
                    for msg in msgs:
                        msg_type = msg.get("type", "text")
                        from_num = str(msg.get("from", ""))
                        msg_id = str(msg.get("id", ""))
                        ts = msg.get("timestamp")
                        if msg_type == "text":
                            text = (msg.get("text") or {}).get("body", "") or " "
                        else:
                            text = " "  # Non-text: placeholder for pipeline; can extend later
                        return (text, from_num, msg_id, ts, name)
        except (KeyError, TypeError, IndexError):
            pass
        return (" ", "", "", None, "")
