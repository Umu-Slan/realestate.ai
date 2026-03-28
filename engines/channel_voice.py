"""
Omnichannel delivery hints for LLM prompts — same brain, channel-appropriate tone and length.
Used by sales/support engines so web, WhatsApp, SMS, social DMs stay coherent.
"""
from __future__ import annotations

# Channels that share the JSON "web-style" adapter (normalize + persistence).
UNIVERSAL_TEXT_CHANNELS: frozenset[str] = frozenset({
    "web",
    "demo",
    "widget",
    "mobile_app",
    "facebook",
    "instagram",
    "messenger",
    "telegram",
    "sms",
    "email",
    "linkedin",
    "tiktok",
    "twitter",
    "x",
})


def normalize_channel_name(channel: str | None) -> str:
    c = (channel or "web").strip().lower()
    if c in UNIVERSAL_TEXT_CHANNELS:
        return c
    if c == "whatsapp":
        return "whatsapp"
    return "web"


def format_channel_context_for_llm(channel: str | None) -> str:
    """
    Short block appended to sales/support system context. Model sees CHANNEL + DELIVERY rules.
    """
    c = normalize_channel_name(channel)
    rules: list[str] = [f"CHANNEL: {c}"]

    if c == "whatsapp":
        rules.append(
            "DELIVERY (WhatsApp): 1–2 short paragraphs max; plain text only (no markdown); "
            "warm Egyptian/Gulf Arabic or English matching the user; end with ONE clear next step "
            "(question or CTA: معاينة، اتصال، إرسال تفاصيل). No bullet walls."
        )
    elif c == "sms":
        rules.append(
            "DELIVERY (SMS): Under ~300 characters when possible; one idea; one question or CTA; no formatting."
        )
    elif c in ("facebook", "instagram", "messenger", "telegram", "tiktok", "linkedin", "twitter", "x"):
        rules.append(
            f"DELIVERY ({c}): Concise DM style; friendly; no internal jargon; one follow-up question or CTA; "
            "match user language (Arabic/English)."
        )
    elif c == "email":
        rules.append(
            "DELIVERY (email): Slightly more structure allowed (greeting + 1–2 short paragraphs + signature line); "
            "still no internal strategy labels; professional consultant tone."
        )
    else:
        rules.append(
            "DELIVERY (web/chat widget): Clear paragraphs; optional short bullets if listing 2–3 projects; "
            "always move toward qualification or next action (visit, call, brochure)."
        )

    rules.append(
        "OMNICHANNEL: Same customer may switch channels; never contradict prior stated budget/location; "
        "if unsure, ask one clarifying question instead of repeating a full pitch."
    )
    return "\n".join(rules)
