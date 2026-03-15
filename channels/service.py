"""
Channel processing service.
Normalizes inbound via adapters, feeds canonical orchestration path.
WhatsApp: full pipeline + persistence + outbound. Web: lightweight orchestration only.
"""
import logging
from typing import Any, Optional

from channels.schema import NormalizedInboundMessage
from channels.adapters.web import WebChannelAdapter
from channels.adapters.whatsapp import WhatsAppChannelAdapter

logger = logging.getLogger(__name__)

ADAPTERS = {
    "web": WebChannelAdapter(),
    "demo": WebChannelAdapter(),
    "whatsapp": WhatsAppChannelAdapter(),
}

_whatsapp_provider = None


def get_whatsapp_provider():
    """Lazy load WhatsApp outbound provider."""
    global _whatsapp_provider
    if _whatsapp_provider is None:
        from channels.providers.whatsapp import WhatsAppStubProvider
        _whatsapp_provider = WhatsAppStubProvider()
    return _whatsapp_provider


def get_adapter(channel: str):
    adapter = ADAPTERS.get((channel or "web").lower())
    if not adapter:
        adapter = WebChannelAdapter()
    return adapter


def normalize_inbound(channel: str, raw_payload: dict[str, Any]) -> NormalizedInboundMessage:
    """
    Normalize raw payload via channel adapter.
    Raises ValueError if payload invalid.
    """
    adapter = get_adapter(channel)
    return adapter.normalize(raw_payload)


def process_inbound_message(
    channel: str,
    raw_payload: dict[str, Any],
    *,
    run_orchestration_kwargs: Optional[dict] = None,
    persist: bool = True,
) -> tuple[NormalizedInboundMessage, Any]:
    """
    Normalize inbound and process. Single entry point for all channels.
    Same multi-agent orchestration for web and WhatsApp when persist=True.
    - persist=True: canonical pipeline + persistence (default)
    - persist=False: orchestration only, no DB writes (testing)
    Returns (NormalizedInboundMessage, OrchestrationRun).
    """
    msg = normalize_inbound(channel, raw_payload)
    try:
        from core.observability import log_inbound
        log_inbound(
            channel=channel,
            external_id=msg.external_id or msg.phone or "-",
            content_len=len(msg.content or ""),
        )
    except ImportError:
        pass

    if channel.lower() == "whatsapp":
        return _process_whatsapp_inbound(msg, run_orchestration_kwargs or {})

    if persist:
        return _process_web_inbound_with_persistence(msg, run_orchestration_kwargs or {})
    return _process_web_inbound_lightweight(msg, run_orchestration_kwargs or {})


def _process_web_inbound_with_persistence(
    msg: NormalizedInboundMessage,
    extra_kwargs: dict,
) -> tuple[NormalizedInboundMessage, Any]:
    """Web: same canonical pipeline + persistence as WhatsApp."""
    from orchestration.service import run_canonical_pipeline_for_channel
    extra = msg.metadata or {}
    response_text, run, _user_msg, _assistant_msg = run_canonical_pipeline_for_channel(
        msg,
        response_mode=extra.get("response_mode"),
        sales_mode=extra.get("sales_mode", "warm_lead"),
        is_angry=extra.get("is_angry", False),
        support_category=extra.get("support_category", ""),
        qualification_override=extra.get("qualification_override"),
        use_llm=extra.get("use_llm", True),
        lang=extra.get("lang", "ar"),
        **extra_kwargs,
    )
    return msg, run


def _process_web_inbound_lightweight(
    msg: NormalizedInboundMessage,
    extra_kwargs: dict,
) -> tuple[NormalizedInboundMessage, Any]:
    """Web: orchestration only, no persistence (backward compat for testing)."""
    params = msg.to_orchestration_params()
    if extra_kwargs:
        params.update(extra_kwargs)
    from orchestration.orchestrator import run_orchestration
    run = run_orchestration(**params, use_multi_agent=True)
    return msg, run


def _process_whatsapp_inbound(
    msg: NormalizedInboundMessage,
    extra_kwargs: dict,
) -> tuple[NormalizedInboundMessage, Any]:
    """WhatsApp: canonical pipeline + outbound. Failure-safe with logging."""
    from orchestration.service import run_canonical_pipeline_for_channel
    from channels.providers.whatsapp import format_outbound_text

    extra = msg.metadata or {}
    response_mode = extra.get("response_mode")
    sales_mode = extra.get("sales_mode", "warm_lead")
    is_angry = extra.get("is_angry", False)
    support_category = extra.get("support_category", "")
    qualification_override = extra.get("qualification_override")
    use_llm = extra.get("use_llm", True)
    lang = extra.get("lang", "ar")

    try:
        response_text, run, _user_msg, _assistant_msg = run_canonical_pipeline_for_channel(
            msg,
            response_mode=response_mode,
            sales_mode=sales_mode,
            is_angry=is_angry,
            support_category=support_category,
            qualification_override=qualification_override,
            use_llm=use_llm,
            lang=lang,
            **extra_kwargs,
        )
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="whatsapp_pipeline", exc=e, stage="run_canonical_pipeline_for_channel")
        except ImportError:
            pass
        logger.exception("WhatsApp pipeline failed: %s", e)
        raise

    # Outbound
    phone = msg.phone or msg.metadata.get("phone", "")
    reply_to = msg.external_message_id or ""
    if phone:
        try:
            provider = get_whatsapp_provider()
            formatted = format_outbound_text(response_text)
            result = provider.send_text(phone, formatted, reply_to_message_id=reply_to or None)
            if not result.success:
                logger.warning("WhatsApp outbound failed: %s", result.error)
        except Exception as e:
            logger.exception("WhatsApp outbound error: %s", e)

    return msg, run
