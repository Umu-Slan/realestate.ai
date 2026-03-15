"""
Production observability: structured logging with correlation/conversation context.
Use for diagnostics and tracing in production.
"""
import json
import logging
import traceback
from contextvars import ContextVar
from typing import Any, Optional


class ObservabilityFormatter(logging.Formatter):
    """
    Formatter that appends structured obs payload (JSON) when present.
    Enables log aggregation tools to parse correlation_id, run_id, event, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        obs = getattr(record, "obs", None)
        if obs and isinstance(obs, dict):
            try:
                return f"{base} | obs={json.dumps(obs)}"
            except (TypeError, ValueError):
                return base
        return base

# Request-scoped context (set by middleware, used in pipeline)
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_conversation_id: ContextVar[Optional[int]] = ContextVar("conversation_id", default=None)
_run_id: ContextVar[str] = ContextVar("run_id", default="")

OBS_LOG = "realestate.observability"
_logger = logging.getLogger(OBS_LOG)


def get_context() -> dict:
    """Get current context for log attachment."""
    ctx = {}
    if cid := _correlation_id.get():
        ctx["correlation_id"] = cid
    if conv_id := _conversation_id.get():
        ctx["conversation_id"] = conv_id
    if rid := _run_id.get():
        ctx["run_id"] = rid
    return ctx


def bind_context(
    correlation_id: str = "",
    conversation_id: Optional[int] = None,
    run_id: str = "",
) -> None:
    """Set context for current request/task."""
    if correlation_id:
        _correlation_id.set(correlation_id)
    if conversation_id is not None:
        _conversation_id.set(conversation_id)
    if run_id:
        _run_id.set(run_id)


def clear_context() -> None:
    """Clear context (call at end of request)."""
    try:
        _correlation_id.set("")
        _conversation_id.set(None)
        _run_id.set("")
    except LookupError:
        pass


def _log_event(level: str, event: str, **kwargs: Any) -> None:
    """Emit structured log. Sensitive data truncated."""
    payload = {"event": event, **get_context(), **kwargs}
    # Truncate long content for safety
    for key in ("content", "message", "raw_content", "error"):
        if key in payload and isinstance(payload[key], str) and len(payload[key]) > 500:
            payload[key] = payload[key][:500] + "..."
    msg = f"{event}"
    extra = {"obs": payload}
    if level == "info":
        _logger.info(msg, extra=extra)
    elif level == "warning":
        _logger.warning(msg, extra=extra)
    else:
        _logger.error(msg, extra=extra)


def log_inbound(
    channel: str,
    external_id: str = "",
    conversation_id: Optional[int] = None,
    content_len: int = 0,
    **kwargs: Any,
) -> None:
    """Log inbound message receipt."""
    _log_event(
        "info",
        "inbound_message",
        channel=channel,
        external_id=external_id or "-",
        conversation_id=conversation_id,
        content_len=content_len,
        **kwargs,
    )


def log_orchestration_start(run_id: str, channel: str, conversation_id: Optional[int] = None, **kwargs: Any) -> None:
    """Log orchestration pipeline start."""
    bind_context(run_id=run_id, conversation_id=conversation_id)
    _log_event("info", "orchestration_start", run_id=run_id, channel=channel, **kwargs)


def log_orchestration_complete(
    run_id: str,
    status: str = "success",
    route: str = "",
    temperature: str = "",
    **kwargs: Any,
) -> None:
    """Log orchestration pipeline completion."""
    _log_event(
        "info",
        "orchestration_complete",
        run_id=run_id,
        status=status,
        route=route or "-",
        temperature=temperature or "-",
        **kwargs,
    )


def log_orchestration_failed(run_id: str, reason: str, stage: str = "", **kwargs: Any) -> None:
    """Log orchestration failure."""
    _log_event("error", "orchestration_failed", run_id=run_id, reason=reason, stage=stage, **kwargs)


def log_scoring(customer_id: int, score: int, temperature: str, **kwargs: Any) -> None:
    """Log lead scoring outcome."""
    _log_event("info", "scoring", customer_id=customer_id, score=score, temperature=temperature, **kwargs)


def log_recommendation(customer_id: int, conversation_id: int, match_count: int, **kwargs: Any) -> None:
    """Log recommendation engine outcome."""
    _log_event(
        "info",
        "recommendation",
        customer_id=customer_id,
        conversation_id=conversation_id,
        match_count=match_count,
        **kwargs,
    )


def log_support_case_created(case_id: int, customer_id: int, category: str, **kwargs: Any) -> None:
    """Log support case creation."""
    _log_event("info", "support_case_created", case_id=case_id, customer_id=customer_id, category=category, **kwargs)


def log_escalation_created(escalation_id: int, customer_id: int, reason: str, **kwargs: Any) -> None:
    """Log escalation creation."""
    _log_event("info", "escalation_created", escalation_id=escalation_id, customer_id=customer_id, reason=reason, **kwargs)


def log_lead_temperature_assigned(
    customer_id: int,
    temperature: str,
    score: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """Log lead temperature assignment (hot/warm/cold/nurture)."""
    _log_event("info", "lead_temperature_assigned", customer_id=customer_id, temperature=temperature, score=score, **kwargs)


def log_buyer_stage_assigned(
    journey_stage: str,
    customer_type: str = "",
    **kwargs: Any,
) -> None:
    """Log buyer journey stage assignment (awareness/consideration/visit_planning)."""
    _log_event("info", "buyer_stage_assigned", journey_stage=journey_stage, customer_type=customer_type or "-", **kwargs)


def log_next_best_action_selected(
    action: str,
    reason: str = "",
    **kwargs: Any,
) -> None:
    """Log next best action selection."""
    _log_event("info", "next_best_action_selected", action=action, reason=reason or "-", **kwargs)


def log_recommendation_generated(
    match_count: int,
    customer_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """Log recommendation engine output (matches generated)."""
    _log_event(
        "info",
        "recommendation_generated",
        match_count=match_count,
        customer_id=customer_id,
        conversation_id=conversation_id,
        **kwargs,
    )


def log_support_severity_assigned(
    case_id: int,
    severity: str,
    category: str = "",
    **kwargs: Any,
) -> None:
    """Log support case severity assignment."""
    _log_event("info", "support_severity_assigned", case_id=case_id, severity=severity, category=category or "-", **kwargs)


def log_escalation_triggered(
    escalation_id: int,
    customer_id: int,
    reason: str,
    **kwargs: Any,
) -> None:
    """Log escalation trigger (business event)."""
    _log_event("info", "escalation_triggered", escalation_id=escalation_id, customer_id=customer_id, reason=reason, **kwargs)


def log_unverified_fact_blocked(
    block_reason: str = "unverified_data",
    intent_hint: str = "",
    **kwargs: Any,
) -> None:
    """Log when response was blocked/rewritten due to unverified pricing or availability."""
    _log_event("info", "unverified_fact_blocked", block_reason=block_reason, intent_hint=intent_hint or "-", **kwargs)


def log_crm_sync(customer_id: int, action: str, **kwargs: Any) -> None:
    """Log CRM sync action."""
    _log_event("info", "crm_sync", customer_id=customer_id, action=action, **kwargs)


def log_pipeline_failure(component: str, error: str, **kwargs: Any) -> None:
    """Log pipeline or component failure."""
    _log_event("error", "pipeline_failure", component=component, error=error, **kwargs)


def log_exception(
    component: str,
    exc: BaseException,
    stage: str = "",
    *,
    traceback_limit: int = 4000,
    **kwargs: Any,
) -> None:
    """
    Log critical exception with full diagnostics for production failure diagnosis.
    Includes: exception_type, error, traceback, stage/component, correlation_id,
    conversation_id, run_id. Keeps logs structured and readable.
    """
    tb_str = traceback.format_exc()
    if len(tb_str) > traceback_limit:
        tb_str = tb_str[:traceback_limit] + "\n... (truncated)"

    err_msg = str(exc)
    if len(err_msg) > 500:
        err_msg = err_msg[:500] + "..."

    payload = {
        "event": "exception",
        "component": component,
        "stage": stage or component,
        "exception_type": type(exc).__name__,
        "error": err_msg,
        "traceback": tb_str,
        **get_context(),
        **kwargs,
    }
    _logger.error("exception", extra={"obs": payload}, exc_info=False)
