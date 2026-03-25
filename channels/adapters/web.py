"""Web channel adapter - website chat and demo flow."""
from typing import Any, Optional

from channels.schema import NormalizedInboundMessage
from channels.adapters.base import BaseChannelAdapter


def _safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely coerce to int for IDs. Returns default if invalid."""
    if val is None:
        return default
    if isinstance(val, int) and not isinstance(val, bool):
        return val if val >= 0 else default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


class WebChannelAdapter(BaseChannelAdapter):
    channel_name = "web"

    def normalize(self, raw_payload: dict) -> NormalizedInboundMessage:
        content = str(raw_payload.get("content", "")).strip()
        if not content:
            raise ValueError("content is required")
        channel = str(raw_payload.get("channel", "web")).lower()
        if channel not in ("web", "demo"):
            channel = "web"
        meta = {
            "conversation_history": raw_payload.get("conversation_history"),
            "use_llm": raw_payload.get("use_llm", True),
            "response_mode": raw_payload.get("response_mode"),
            "sales_mode": raw_payload.get("sales_mode"),
            "is_angry": raw_payload.get("is_angry"),
            "support_category": raw_payload.get("support_category"),
            "qualification_override": raw_payload.get("qualification_override"),
            "lang": raw_payload.get("lang", "ar"),
        }
        # UTM + geo + referrer (lead intelligence / campaign tracking)
        _attr_keys = (
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "referrer", "landing_page", "country", "region", "city",
            "gclid", "fbclid",
        )
        for key in _attr_keys:
            val = raw_payload.get(key)
            if val is not None and str(val).strip():
                meta[key] = val
        if isinstance(raw_payload.get("attribution"), dict):
            meta["attribution"] = raw_payload["attribution"]
        # Legacy top-level keys for extract_attribution_payload
        if raw_payload.get("campaign"):
            meta["campaign"] = raw_payload["campaign"]
        if raw_payload.get("source"):
            meta["source"] = raw_payload["source"]
        return NormalizedInboundMessage(
            content=content,
            source_channel=channel,
            external_id=str(raw_payload.get("external_id", "")).strip(),
            phone=str(raw_payload.get("phone", "")).strip(),
            email=str(raw_payload.get("email", "")).strip(),
            name=str(raw_payload.get("name", "")).strip(),
            campaign=str(raw_payload.get("campaign", "")).strip(),
            source=str(raw_payload.get("source", "")).strip(),
            conversation_id=_safe_int(raw_payload.get("conversation_id")),
            customer_id=_safe_int(raw_payload.get("customer_id")),
            metadata=meta,
        )
