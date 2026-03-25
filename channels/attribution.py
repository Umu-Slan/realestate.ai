"""
Lead attribution: UTM, referrer, landing page, geo — stored on Conversation + Customer.

Designed for campaign/channel/geo intelligence in the console. First-touch per conversation;
customer keeps attribution_first (set once) and attribution_last (latest merge).
"""
from __future__ import annotations

from typing import Any

# Standard marketing params + optional geo (from widget, CRM, or IP geo service on client).
_ATTRIBUTION_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "referrer",
        "landing_page",
        "country",
        "region",
        "city",
        "gclid",
        "fbclid",
    }
)


def extract_attribution_payload(meta: dict[str, Any] | None) -> dict[str, str]:
    """Normalize attribution dict from message metadata or raw API fields."""
    if not meta:
        return {}
    out: dict[str, str] = {}

    nested = meta.get("attribution")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            s = str(v).strip()
            if s:
                out[str(k).lower()] = s[:500]

    for k in _ATTRIBUTION_KEYS:
        v = meta.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out[k] = s[:500]

    # Adapter top-level campaign/source (legacy)
    if meta.get("campaign") and "utm_campaign" not in out:
        s = str(meta["campaign"]).strip()
        if s:
            out["utm_campaign"] = s[:500]
    if meta.get("source") and "utm_source" not in out:
        s = str(meta["source"]).strip()
        if s:
            out["utm_source"] = s[:500]
    return out


def apply_attribution_to_models(customer, conversation, meta: dict[str, Any] | None) -> None:
    """Persist attribution on conversation (first keys win) and customer (first + last)."""
    extracted = extract_attribution_payload(meta or {})
    if not extracted:
        return

    cm = dict(conversation.metadata or {})
    att = dict(cm.get("attribution") or {})
    for k, v in extracted.items():
        att.setdefault(k, v)
    cm["attribution"] = att
    if cm != (conversation.metadata or {}):
        conversation.metadata = cm
        conversation.save(update_fields=["metadata"])

    cust_meta = dict(customer.metadata or {})
    if not cust_meta.get("attribution_first"):
        cust_meta["attribution_first"] = dict(extracted)
    last = dict(cust_meta.get("attribution_last") or {})
    last.update(extracted)
    cust_meta["attribution_last"] = last
    if cust_meta != (customer.metadata or {}):
        customer.metadata = cust_meta
        customer.save(update_fields=["metadata"])


def campaign_bucket_label(att: dict[str, str] | None) -> str:
    """Human-facing segment key for charts and tables."""
    if not att:
        return "organic / unknown"
    c = (att.get("utm_campaign") or "").strip()
    if c:
        return c
    src, med = (att.get("utm_source") or "").strip(), (att.get("utm_medium") or "").strip()
    if src or med:
        return f"{src or '?'} / {med or '?'}"
    if att.get("referrer"):
        ref = att["referrer"][:80]
        return ref + ("…" if len(att["referrer"]) > 80 else "")
    return "organic / unknown"


def geo_bucket_label(att: dict[str, str] | None) -> str:
    if not att:
        return "—"
    parts = [att.get("city"), att.get("region"), att.get("country")]
    parts = [p.strip() for p in parts if p and str(p).strip()]
    if not parts:
        return "—"
    return ", ".join(parts[:3])
