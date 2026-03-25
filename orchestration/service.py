"""
Canonical orchestration service - single entry point for all inbound interactions.
Runs full pipeline with persistence (Customer, Conversation, Message, OrchestrationSnapshot).
- run_canonical_pipeline: web/demo (request-based)
- run_canonical_pipeline_for_channel: WhatsApp and other channels (NormalizedInboundMessage)
"""
from typing import Optional, TYPE_CHECKING

from django.db import transaction

from engines.demo_persistence import get_or_create_demo_conversation
from conversations.models import Message
from orchestration.orchestrator import run_orchestration
from orchestration.schemas import OrchestrationRun

if TYPE_CHECKING:
    from channels.schema import NormalizedInboundMessage


def _build_conversation_history(conversation, limit: int = 12) -> list[dict]:
    """Get recent messages as [{"role": "...", "content": "..."}]."""
    messages = conversation.messages.order_by("-created_at")[:limit]
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def _sanitize_for_customer(text: str, user_content: str = "") -> str:
    """Remove internal strategy/debug text. Use fallback if result is empty or too short."""
    if not text or not isinstance(text, str):
        text = ""
    try:
        from engines.response_sanitizer import sanitize_customer_response
        from engines.lang_utils import detect_response_language
        cleaned = sanitize_customer_response(text.strip())
        if cleaned and len(cleaned.strip()) >= 10:
            return cleaned
        lang = detect_response_language(user_content) if user_content else "ar"
        if lang == "ar":
            return "أهلاً! سعيد بتواصلك. كيف أستطيع مساعدتك اليوم؟"
        return "Hello! Glad to help. How can I assist you today?"
    except Exception:
        return text or "أهلاً! كيف يمكنني مساعدتك؟"


@transaction.atomic
def run_canonical_pipeline(
    request,
    content: str,
    *,
    response_mode: Optional[str] = None,  # "sales" | "support" | "recommendation" | None
    sales_mode: str = "warm_lead",
    is_angry: bool = False,
    support_category: str = "",
    qualification_override: Optional[dict] = None,
    use_llm: bool = True,
    lang: str = "ar",
) -> tuple[str, OrchestrationRun, Optional[Message], Optional[Message]]:
    """
    Run full canonical pipeline with persistence.
    Returns (response_text, run, user_msg, assistant_msg).
    """
    customer, conversation = get_or_create_demo_conversation(request)
    try:
        from core.observability import log_inbound, bind_context
        log_inbound(
            channel="web",
            external_id=customer.identity.external_id if customer.identity else f"web:{conversation.id}",
            conversation_id=conversation.id,
            content_len=len(content),
        )
        bind_context(conversation_id=conversation.id)
    except ImportError:
        pass
    history = _build_conversation_history(conversation)
    external_id = (
        customer.identity.external_id
        if customer.identity
        else f"web:{conversation.id}"
    )

    user_msg = Message.objects.create(
        conversation=conversation,
        role="user",
        content=content,
        metadata={
            "response_mode": response_mode or "generic",
            "sales_mode": sales_mode if response_mode == "sales" else None,
            "is_angry": is_angry if response_mode == "support" else None,
        },
    )

    run = run_orchestration(
        raw_content=content,
        channel="web",
        external_id=external_id,
        conversation_id=conversation.id,
        message_id=user_msg.id,
        conversation_history=history,
        customer_id=customer.id,
        use_llm=use_llm,
        response_mode=response_mode,
        sales_mode=sales_mode,
        is_angry=is_angry,
        support_category=support_category,
        qualification_override=qualification_override,
        lang=lang,
        use_multi_agent=True,
    )

    response_text = _sanitize_for_customer(run.final_response or "", content)

    # Persist domain artifacts (LeadScore, LeadQualification, Recommendation, etc.)
    try:
        from orchestration.persistence import persist_orchestration_artifacts
        persist_orchestration_artifacts(
            run,
            customer_id=customer.id,
            conversation_id=conversation.id,
            user_message_id=user_msg.id,
            mode=response_mode or "generic",
            source_channel="web",
            is_angry=is_angry,
        )
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(
                component="persistence",
                exc=e,
                stage="persist_orchestration_artifacts",
                run_id=run.run_id,
                conversation_id=conversation.id,
                customer_id=customer.id,
            )
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("Persistence of orchestration artifacts failed: %s", e)

    # Update user message with intent/confidence for audit
    intent_primary = run.intent_result.get("primary", "")
    conf = run.intent_result.get("confidence", 0)
    conf_level = "high" if conf >= 0.7 else "medium" if conf >= 0.5 else "low" if conf > 0 else "unknown"
    # Map IntentCategory to IntentType for Message model
    intent_map = {
        "project_inquiry": "project_inquiry", "price_inquiry": "pricing",
        "schedule_visit": "schedule_visit", "brochure_request": "general_info",
        "support_complaint": "support", "contract_issue": "support",
        "maintenance_issue": "support", "delivery_inquiry": "support",
        "general_support": "support", "spam": "spam",
    }
    user_msg.intent = intent_map.get(intent_primary, "other") if intent_primary else ""
    user_msg.intent_confidence = conf_level
    meta = user_msg.metadata or {}
    meta["intent_primary"] = intent_primary
    user_msg.metadata = meta
    user_msg.save(update_fields=["intent", "intent_confidence", "metadata"])

    # Update conversation metadata with mode
    if response_mode:
        conv_meta = conversation.metadata or {}
        conv_meta["last_mode"] = response_mode
        conversation.metadata = conv_meta
        conversation.save(update_fields=["metadata"])

    # Build assistant metadata: include matches + next_step for conversation restore
    asst_meta = {
        "run_id": run.run_id,
        "response_mode": response_mode or "generic",
        "intent": run.intent_result.get("primary", ""),
        "score": run.scoring.get("score"),
        "temperature": run.scoring.get("temperature", ""),
    }
    matches = getattr(run, "recommendation_matches", []) or []
    rec_result = getattr(run, "recommendation_result", {}) or {}
    if rec_result.get("recommendation_ready") and matches:
        asst_meta["matches"] = [dict(m) for m in matches][:10]
    rt = run.routing or {}
    sc = run.scoring or {}
    raw_next = rt.get("recommended_cta") or sc.get("next_best_action", "") or rt.get("next_sales_move", "")
    if raw_next:
        try:
            from engines.cta_mapping import to_customer_facing_next_step
            ns = to_customer_facing_next_step(raw_next)
            if ns and isinstance(ns, dict):
                asst_meta["next_step"] = ns
        except Exception:
            pass
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=response_text,
        metadata=asst_meta,
    )

    return response_text, run, user_msg, assistant_msg


@transaction.atomic
def run_canonical_pipeline_for_channel(
    normalized_msg: "NormalizedInboundMessage",
    *,
    response_mode: Optional[str] = None,
    sales_mode: str = "warm_lead",
    is_angry: bool = False,
    support_category: str = "",
    qualification_override: Optional[dict] = None,
    use_llm: bool = True,
    lang: str = "ar",
) -> tuple[str, OrchestrationRun, Optional[Message], Optional[Message]]:
    """
    Run canonical pipeline for any channel (web, whatsapp, demo).
    Same multi-agent orchestration for all. Preserves channel metadata.
    """
    from channels.persistence import get_or_create_customer_conversation

    try:
        from companies.services import ensure_default_company
        ensure_default_company()
    except Exception:
        pass
    channel = (normalized_msg.source_channel or "web").lower()
    customer, conversation = get_or_create_customer_conversation(normalized_msg)
    try:
        from channels.attribution import apply_attribution_to_models

        apply_attribution_to_models(customer, conversation, normalized_msg.metadata)
    except Exception:
        pass
    try:
        from core.observability import log_inbound, bind_context
        log_inbound(
            channel=channel,
            external_id=normalized_msg.external_id or normalized_msg.phone or f"{channel}:{conversation.id}",
            conversation_id=conversation.id,
            content_len=len(normalized_msg.content or ""),
        )
        bind_context(conversation_id=conversation.id)
    except ImportError:
        pass
    history = _build_conversation_history(conversation)
    external_id = (
        customer.identity.external_id
        if customer.identity
        else f"{channel}:{conversation.id}"
    )

    meta = normalized_msg.to_channel_metadata() if hasattr(normalized_msg, "to_channel_metadata") else dict(normalized_msg.metadata or {})
    meta["response_mode"] = response_mode or "generic"
    meta["sales_mode"] = sales_mode if response_mode == "sales" else None
    meta["is_angry"] = is_angry if response_mode == "support" else None

    user_msg = Message.objects.create(
        conversation=conversation,
        role="user",
        content=normalized_msg.content,
        metadata=meta,
    )

    run = run_orchestration(
        raw_content=normalized_msg.content,
        channel=channel,
        external_id=external_id,
        conversation_id=conversation.id,
        message_id=user_msg.id,
        conversation_history=history,
        customer_id=customer.id,
        use_llm=use_llm,
        response_mode=response_mode,
        sales_mode=sales_mode,
        is_angry=is_angry,
        support_category=support_category,
        qualification_override=qualification_override,
        lang=lang,
        phone=normalized_msg.phone,
        email=normalized_msg.email,
        name=normalized_msg.name,
        use_multi_agent=True,
    )

    response_text = _sanitize_for_customer(
        run.final_response or "",
        normalized_msg.content if hasattr(normalized_msg, "content") else "",
    )

    try:
        from orchestration.persistence import persist_orchestration_artifacts
        persist_orchestration_artifacts(
            run,
            customer_id=customer.id,
            conversation_id=conversation.id,
            user_message_id=user_msg.id,
            mode=response_mode or "generic",
            source_channel=channel,
            is_angry=is_angry,
        )
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(
                component="persistence",
                exc=e,
                stage="persist_orchestration_artifacts",
                run_id=run.run_id,
                conversation_id=conversation.id,
                customer_id=customer.id,
            )
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("Persistence of orchestration artifacts failed: %s", e)

    intent_primary = run.intent_result.get("primary", "")
    conf = run.intent_result.get("confidence", 0)
    conf_level = "high" if conf >= 0.7 else "medium" if conf >= 0.5 else "low" if conf > 0 else "unknown"
    intent_map = {
        "project_inquiry": "project_inquiry", "price_inquiry": "pricing",
        "schedule_visit": "schedule_visit", "brochure_request": "general_info",
        "support_complaint": "support", "contract_issue": "support",
        "maintenance_issue": "support", "delivery_inquiry": "support",
        "general_support": "support", "spam": "spam",
    }
    user_msg.intent = intent_map.get(intent_primary, "other") if intent_primary else ""
    user_msg.intent_confidence = conf_level
    user_meta = user_msg.metadata or {}
    user_meta["intent_primary"] = intent_primary
    user_msg.metadata = user_meta
    user_msg.save(update_fields=["intent", "intent_confidence", "metadata"])

    if response_mode:
        conv_meta = conversation.metadata or {}
        conv_meta["last_mode"] = response_mode
        conversation.metadata = conv_meta
        conversation.save(update_fields=["metadata"])

    assistant_msg = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=response_text,
        metadata={
            "run_id": run.run_id,
            "response_mode": response_mode or "generic",
            "intent": run.intent_result.get("primary", ""),
            "score": run.scoring.get("score"),
            "temperature": run.scoring.get("temperature", ""),
        },
    )

    return response_text, run, user_msg, assistant_msg
