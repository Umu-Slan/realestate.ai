"""
Multi-agent orchestration runner.
Runs the agent pipeline and maps outputs to OrchestrationRun.
Reuses policy, next_action, handoff, persistence from main orchestrator.
"""
import logging
from typing import Optional

from orchestration.agents.base import AgentContext
from orchestration.agents.registry import run_agent_pipeline
from orchestration.agents.bootstrap import DEFAULT_AGENT_PIPELINE
from orchestration.schemas import OrchestrationRun, IntakeInput
from orchestration.states import PipelineStage, RunStatus

logger = logging.getLogger(__name__)


def run_multi_agent_pipeline(
    raw_content: str,
    *,
    channel: str = "web",
    external_id: str = "",
    phone: str = "",
    email: str = "",
    name: str = "",
    conversation_id: Optional[int] = None,
    conversation_history: Optional[list] = None,
    customer_id: Optional[int] = None,
    response_mode: Optional[str] = None,
    qualification_override: Optional[dict] = None,
    use_llm: bool = True,
    lang: str = "ar",
    is_angry: bool = False,
) -> OrchestrationRun:
    """
    Run multi-agent pipeline and return OrchestrationRun.
    Does NOT run policy/next_action/handoff - caller (orchestrator) does that.
    """
    from orchestration.orchestrator import _normalize_intake
    run_id = f"run_multi_{__import__('uuid').uuid4().hex[:12]}"
    run = OrchestrationRun(run_id=run_id)

    # Stage 1: Intake
    intake = _normalize_intake(
        raw_content, channel, external_id, phone, email, name, conversation_id
    )
    run.intake = intake
    if not intake.normalized_content:
        run.status = RunStatus.FAILED
        run.failure_reason = "empty_content"
        run.current_stage = PipelineStage.FAILED
        return run

    # Stage 2: Identity (same as orchestrator)
    identity_info = {}
    try:
        from leads.services.identity_resolution import resolve_identity
        result = resolve_identity(phone=phone or None, email=email or None, external_id=external_id or None)
        identity_info = {
            "matched": result.matched,
            "identity_id": result.identity.id if result.identity else None,
            "customer_type_hint": "existing" if result.matched else "new",
        }
    except Exception as e:
        logger.warning("Identity resolution failed: %s", e)
        identity_info = {"error": str(e)}
    run.identity_resolution = identity_info

    # Build agent context
    ctx = AgentContext(
        run_id=run_id,
        message_text=intake.normalized_content,
        conversation_history=list(conversation_history or []),
        channel=channel,
        external_id=external_id,
        customer_id=customer_id,
        conversation_id=conversation_id,
        response_mode=response_mode,
        qualification_override=qualification_override,
        use_llm=use_llm,
        lang=lang,
        is_angry=is_angry,
        identity_resolution=identity_info,
    )

    # Run agent pipeline
    pipeline = DEFAULT_AGENT_PIPELINE
    ctx, results = run_agent_pipeline(pipeline, ctx, stop_on_failure=False)

    # Map agent outputs to OrchestrationRun
    run.intent_result = ctx.intent_output or {}
    run.qualification = ctx.get_qualification()
    run.memory = ctx.memory_output or {}
    strategy = ctx.sales_strategy_output or {}
    routing = ctx.routing_output or {}
    run.routing = dict(routing)
    run.routing["customer_type"] = routing.get("customer_type", "new_lead")
    # CTA for customer-facing UI (prefer clean recommended_cta over action:reason)
    if strategy.get("recommended_cta"):
        run.routing["recommended_cta"] = strategy["recommended_cta"]

    # Journey stage from agent (persist + operator UI)
    js = ctx.journey_stage_output or {}
    run.journey_stage = js.get("stage", "")
    if run.journey_stage == "support":
        run.journey_stage = "support_retention"  # enum value for persistence
    run.routing["stage_reasoning"] = js.get("stage_reasoning", [])
    run.routing["next_sales_move"] = js.get("next_sales_move", "")
    run.routing["approach"] = strategy.get("approach", "")
    run.routing["objection_key"] = strategy.get("objection_key", "")

    scoring = strategy.get("scoring", {})
    run.scoring = {
        "score": scoring.get("score", 0),
        "temperature": scoring.get("temperature", "nurture"),
        "confidence": scoring.get("confidence", "unknown"),
        "next_best_action": scoring.get("next_best_action", "") or strategy.get("next_best_action", ""),
        "recommended_route": scoring.get("recommended_route", "nurture"),
        "reason_codes": scoring.get("reason_codes", []),
    }

    # Retrieval
    retrieval = ctx.retrieval_output or {}
    run.retrieval_plan = {
        "query": retrieval.get("query", ""),
        "document_types": retrieval.get("document_types", []),
        "retrieval_error": retrieval.get("retrieval_error"),
    }
    run.retrieval_sources = retrieval.get("retrieval_sources", [])
    run.has_verified_pricing = retrieval.get("has_verified_pricing", False)
    run.has_verified_availability = retrieval.get("has_verified_availability", False)

    # Recommendation mode + sales mode (when qualified): use recommendation output
    # Only populate recommendation_matches when recommendation_ready (eligibility passed)
    rec = ctx.recommendation_output or {}
    rec_ready = rec.get("recommendation_ready", False)
    matches = rec.get("top_recommendations") or rec.get("matches", [])
    if response_mode == "recommendation" and rec_ready:
        run.recommendation_matches = matches
        run.retrieval_sources = run.recommendation_matches
    elif response_mode == "sales" and rec_ready and matches:
        # Sales mode: populate matches only when qualified (budget+location) for project cards
        run.recommendation_matches = matches
    run.recommendation_result = {
        "recommendation_ready": rec_ready,
        "recommendation_block_reason": rec.get("recommendation_block_reason", ""),
        "top_recommendations": rec.get("top_recommendations") or rec.get("matches", []),
        "why_it_matches": [m.get("why_it_matches", m.get("match_reasons", [])) for m in (rec.get("top_recommendations") or rec.get("matches", []))],
        "tradeoffs": [m.get("tradeoffs", m.get("trade_offs", [])) for m in (rec.get("top_recommendations") or rec.get("matches", []))],
        "overall_confidence": rec.get("overall_confidence", 0),
        "recommendation_confidence": rec.get("recommendation_confidence", rec.get("overall_confidence", 0)),
        "alternatives": rec.get("alternatives", []),
        "qualification_summary": rec.get("qualification_summary", ""),
        "data_completeness": rec.get("data_completeness", "minimal"),
    }

    # Response from composer (reply_text primary, draft_response backward compat)
    composer = ctx.response_composer_output or {}
    run.draft_response = composer.get("reply_text", "") or composer.get("draft_response", "")

    # Safe response policy from retrieval
    from orchestration.policy_engine import intent_primary_is_strict_price_inquiry

    intent_primary = (run.intent_result.get("primary") or "").lower()
    msg_lower = (intake.normalized_content or "").lower()
    is_price_inquiry = intent_primary_is_strict_price_inquiry(intent_primary)
    is_availability_inquiry = (
        "availability" in intent_primary or
        any(kw in msg_lower for kw in ("متوفر", "متبقى", "وحدة متبقية", "availability", "units left"))
    )
    if is_price_inquiry and not run.has_verified_pricing:
        run.routing["safe_response_policy"] = True
    if is_availability_inquiry and not run.has_verified_availability:
        run.routing["unavailable_data"] = True
    if retrieval.get("retrieval_error"):
        run.routing["unavailable_data"] = True

    run.current_stage = PipelineStage.RESPONSE_DRAFTING
    return run
