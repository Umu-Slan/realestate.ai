"""
Main orchestrator - controlled pipeline, no swarm.
Single linear flow, audit at each stage, explicit failure handling.
"""
import uuid
import logging
from typing import Optional

from django.conf import settings

from orchestration.states import PipelineStage, RunStatus
from orchestration.schemas import OrchestrationRun, IntakeInput
from orchestration.policy_engine import apply_policy_engine, intent_primary_is_strict_price_inquiry
from orchestration.next_action import compute_next_best_action
from orchestration.handoff import build_handoff_summary
from orchestration.retrieval_planner import plan_retrieval
from orchestration.journey_stage import detect_journey_stage

logger = logging.getLogger(__name__)


SUPPORT_ROUTES = frozenset({"support", "support_escalation", "legal_handoff"})


def _is_support_routing(run: OrchestrationRun) -> bool:
    """True if routing indicates support-related flow (auto support mode)."""
    route = (run.routing or {}).get("route", "")
    return route in SUPPORT_ROUTES


def _log_stage(run: OrchestrationRun, stage: PipelineStage, output: dict) -> None:
    """Audit log for each stage."""
    try:
        from audit.service import log
        entry = log(
            action="orchestration_stage",
            actor="orchestrator",
            subject_type="orchestration_run",
            subject_id=run.run_id,
            payload={"stage": stage.value, "output": output},
        )
        run.audit_log_ids.append(entry.id)
    except Exception as e:
        logger.warning("Audit log failed: %s", e)


def _normalize_intake(
    raw_content: str,
    channel: str = "web",
    external_id: str = "",
    phone: str = "",
    email: str = "",
    name: str = "",
    conversation_id: Optional[int] = None,
) -> IntakeInput:
    """Stage 1: Intake normalization. Applies Arabic normalization for typos/dialects."""
    content = (raw_content or "").strip()
    errors = []
    if not content:
        errors.append("empty_content")
    else:
        try:
            from engines.arabic_normalizer import normalize_arabic_input
            result = normalize_arabic_input(content)
            content = result.normalized or content
        except Exception:
            pass
    if len(content) > 10000:
        content = content[:10000]
        errors.append("truncated")
    return IntakeInput(
        raw_content=raw_content or "",
        normalized_content=content,
        channel=channel or "web",
        external_id=external_id or "anonymous",
        phone=phone or "",
        email=email or "",
        name=name or "",
        conversation_id=conversation_id,
        validation_errors=errors,
    )


def run_orchestration(
    raw_content: str,
    *,
    channel: str = "web",
    external_id: str = "",
    phone: str = "",
    email: str = "",
    name: str = "",
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
    conversation_history: Optional[list[dict]] = None,
    customer_id: Optional[int] = None,
    use_llm: bool = True,
    llm_timeout_seconds: int = 30,
    response_mode: Optional[str] = None,  # "sales" | "support" | "recommendation" | None
    sales_mode: str = "warm_lead",
    is_angry: bool = False,
    support_category: str = "",
    qualification_override: Optional[dict] = None,
    lang: str = "ar",
    use_multi_agent: bool = False,  # Use multi-agent pipeline when True
) -> OrchestrationRun:
    """
    Run full orchestration pipeline. Returns OrchestrationRun with all stage outputs.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    run = OrchestrationRun(run_id=run_id)

    # Normalize conversation_history to avoid iterating over string/dict
    if not isinstance(conversation_history, (list, tuple)):
        conversation_history = []
    conversation_history = list(conversation_history)

    try:
        # Audit start
        from audit.service import log
        log(
            action="orchestration_started",
            actor=external_id or "system",
            subject_type="orchestration_run",
            subject_id=run_id,
            payload={"input_length": len(raw_content or ""), "channel": channel},
            run_id=run_id,
            conversation_id=conversation_id,
        )
        try:
            from core.observability import log_orchestration_start
            log_orchestration_start(run_id=run_id, channel=channel, conversation_id=conversation_id)
        except ImportError:
            pass

        # Stage 1: Intake
        run.intake = _normalize_intake(
            raw_content, channel, external_id, phone, email, name, conversation_id
        )
        run.current_stage = PipelineStage.INTAKE_NORMALIZATION
        _log_stage(run, PipelineStage.INTAKE_NORMALIZATION, {"normalized_len": len(run.intake.normalized_content)})

        if not run.intake.normalized_content:
            run.status = RunStatus.FAILED
            run.failure_reason = "empty_content"
            run.current_stage = PipelineStage.FAILED
            return run

        # Stage 2: Identity/context resolution
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
            try:
                from core.observability import log_exception
                log_exception(component="orchestration", exc=e, stage="identity_resolution", run_id=run_id, conversation_id=conversation_id)
            except ImportError:
                pass
            logger.warning("Identity resolution failed: %s", e)
            identity_info = {"error": str(e)}
        run.identity_resolution = identity_info
        run.current_stage = PipelineStage.IDENTITY_CONTEXT_RESOLUTION
        _log_stage(run, PipelineStage.IDENTITY_CONTEXT_RESOLUTION, identity_info)

        # Multi-agent path: run agent pipeline and merge; then skip to policy
        intel = None  # Used later for requires_clarification when not multi-agent
        if use_multi_agent:
            try:
                from orchestration.multi_agent_runner import run_multi_agent_pipeline
                run_ma = run_multi_agent_pipeline(
                    raw_content,
                    channel=channel,
                    external_id=external_id,
                    phone=phone,
                    email=email,
                    name=name,
                    conversation_id=conversation_id,
                    conversation_history=conversation_history,
                    customer_id=customer_id,
                    response_mode=response_mode,
                    qualification_override=qualification_override,
                    use_llm=use_llm,
                    lang=lang,
                    is_angry=is_angry,
                )
                if run_ma.status == RunStatus.FAILED:
                    run.status = run_ma.status
                    run.failure_reason = run_ma.failure_reason
                    run.current_stage = PipelineStage.FAILED
                    return run
                # Merge multi-agent outputs into run
                run.intent_result = run_ma.intent_result
                run.qualification = run_ma.qualification
                run.memory = getattr(run_ma, "memory", {}) or {}
                run.scoring = run_ma.scoring
                run.routing = run_ma.routing
                run.retrieval_plan = run_ma.retrieval_plan
                run.retrieval_sources = run_ma.retrieval_sources
                run.has_verified_pricing = run_ma.has_verified_pricing
                run.has_verified_availability = run_ma.has_verified_availability
                run.draft_response = run_ma.draft_response
                run.recommendation_matches = run_ma.recommendation_matches
                run.journey_stage = run_ma.journey_stage or ""
                if hasattr(run_ma, "recommendation_result"):
                    run.recommendation_result = run_ma.recommendation_result
                # Synthetic intel for policy/next_action
                intel = type("Intel", (), {
                    "requires_clarification": run.routing.get("requires_human_review", False),
                })()
                run.current_stage = PipelineStage.SCORING_OR_CATEGORIZATION
                _log_stage(run, PipelineStage.SCORING_OR_CATEGORIZATION, {"score": run.scoring.get("score"), "temperature": run.scoring.get("temperature"), "multi_agent": True})
                # Journey stage from agent (already in run.journey_stage); fallback to detect_journey_stage if empty
                if not run.journey_stage:
                    prior_stage = ""
                    if conversation_id:
                        try:
                            from console.models import OrchestrationSnapshot
                            prev = OrchestrationSnapshot.objects.filter(conversation_id=conversation_id).exclude(run_id=run_id).order_by("-created_at").first()
                            if prev and prev.journey_stage:
                                prior_stage = prev.journey_stage
                        except Exception:
                            pass
                    qual = run.qualification or {}
                    run.journey_stage = detect_journey_stage(
                        intent_primary=run.intent_result.get("primary", ""),
                        customer_type=run.routing.get("customer_type", ""),
                        temperature=run.scoring.get("temperature", ""),
                        score=run.scoring.get("score", 0),
                        qualification=qual,
                        routing_route=run.routing.get("route", ""),
                        prior_stage=prior_stage,
                        has_project_preference=bool(qual.get("project_preference")),
                        has_budget=bool(qual.get("budget_min") or qual.get("budget_max")),
                        has_location=bool(qual.get("location_preference")),
                    )
                run.routing["journey_stage"] = run.journey_stage
                # Skip to Stage 8 (policy) - draft is already set
                draft = run.draft_response or ""
                has_verified_pricing = run.has_verified_pricing
                has_verified_availability = run.has_verified_availability
            except Exception as e:
                try:
                    from core.observability import log_exception, log_orchestration_failed
                    log_exception(component="orchestration", exc=e, stage="multi_agent", run_id=run_id, conversation_id=conversation_id)
                    log_orchestration_failed(run_id=run_id, reason=str(e), stage="multi_agent")
                except ImportError:
                    pass
                logger.warning("Multi-agent pipeline failed, falling back to legacy: %s", e)
                use_multi_agent = False  # Fall through to legacy path

        if not use_multi_agent:
            # Stage 3-5: Intelligence (intent, qualification, scoring)
            try:
                from intelligence.services.pipeline import analyze_message
                customer_type_hint = ""
                if response_mode == "support":
                    customer_type_hint = "support_customer"
                elif response_mode == "recommendation":
                    customer_type_hint = "new_lead"
                intel = analyze_message(
                    run.intake.normalized_content,
                    conversation_history=conversation_history or [],
                    customer_id=customer_id,
                    is_existing_customer=identity_info.get("matched", False) or (response_mode == "support"),
                    customer_type=customer_type_hint,
                    is_angry=is_angry,
                    use_llm=use_llm,
                )
            except Exception as e:
                try:
                    from core.observability import log_exception, log_orchestration_failed
                    log_exception(component="orchestration", exc=e, stage="intelligence", run_id=run_id, conversation_id=conversation_id)
                    log_orchestration_failed(run_id=run_id, reason=str(e), stage="intelligence")
                except ImportError:
                    pass
                logger.warning("Intelligence pipeline failed: %s", e)
                run.status = RunStatus.FAILED
                run.failure_reason = f"intelligence_failed: {e}"
                run.current_stage = PipelineStage.FAILED
                _log_stage(run, PipelineStage.FAILED, {"reason": run.failure_reason})
                return run

            # Serialize intelligence to dict for run
            run.intent_result = {
                "primary": intel.intent.primary,
                "secondary": getattr(intel.intent, "secondary", []) or [],
                "confidence": getattr(intel.intent, "confidence", 0),
                "is_support": intel.intent.is_support,
                "is_spam": intel.intent.is_spam,
                "is_broker": intel.intent.is_broker,
            }
            run.qualification = {
                "budget_min": str(q.budget_min) if (q := intel.qualification).budget_min else None,
                "budget_max": str(q.budget_max) if q.budget_max else None,
                "location_preference": q.location_preference,
                "project_preference": q.project_preference,
                "property_type": q.property_type,
                "urgency": q.urgency,
                "missing_fields": q.missing_fields or [],
                "confidence": q.confidence,
            }
            rc = getattr(intel.scoring, "reason_codes", []) or []
            run.scoring = {
            "score": intel.scoring.score,
            "temperature": intel.scoring.temperature,
            "confidence": intel.scoring.confidence,
            "next_best_action": intel.scoring.next_best_action,
            "recommended_route": intel.scoring.recommended_route,
            "reason_codes": [{"factor": r.factor, "contribution": r.contribution, "note": r.note} for r in rc] if rc else [],
            }
            run.routing = {
            "route": intel.routing.route,
            "queue": intel.routing.queue,
            "requires_human_review": intel.routing.requires_human_review,
            "escalation_ready": intel.routing.escalation_ready,
            "quarantine": intel.routing.quarantine,
            "handoff_type": intel.routing.handoff_type,
            "safe_response_policy": intel.routing.safe_response_policy,
            }
            if intel.support_category:
                run.qualification["support_category"] = intel.support_category
            run.routing["customer_type"] = intel.customer_type  # for policy/handoff

            # Override qualification when provided (e.g. recommendation with explicit criteria)
            if qualification_override:
                for k, v in qualification_override.items():
                    if v is not None and v != "":
                        run.qualification[k] = str(v) if not isinstance(v, str) else v

            run.current_stage = PipelineStage.SCORING_OR_CATEGORIZATION
            _log_stage(run, PipelineStage.SCORING_OR_CATEGORIZATION, {"score": run.scoring.get("score"), "temperature": run.scoring.get("temperature")})

            # Stage 5b: Journey stage detection (before retrieval for context)
            prior_stage = ""
            if conversation_id:
                try:
                    from console.models import OrchestrationSnapshot
                    prev = OrchestrationSnapshot.objects.filter(conversation_id=conversation_id).exclude(run_id=run_id).order_by("-created_at").first()
                    if prev and prev.journey_stage:
                        prior_stage = prev.journey_stage
                except Exception:
                    pass
            qual = run.qualification or {}
            run.journey_stage = detect_journey_stage(
                intent_primary=run.intent_result.get("primary", ""),
                customer_type=run.routing.get("customer_type", ""),
                temperature=run.scoring.get("temperature", ""),
                score=run.scoring.get("score", 0),
                qualification=qual,
                routing_route=run.routing.get("route", ""),
                prior_stage=prior_stage,
                has_project_preference=bool(qual.get("project_preference")),
                has_budget=bool(qual.get("budget_min") or qual.get("budget_max")),
                has_location=bool(qual.get("location_preference")),
            )
            run.routing["journey_stage"] = run.journey_stage
            if run.journey_stage:
                try:
                    from core.observability import log_buyer_stage_assigned
                    log_buyer_stage_assigned(
                        journey_stage=run.journey_stage,
                        customer_type=run.routing.get("customer_type", ""),
                        run_id=run_id,
                        conversation_id=conversation_id,
                    )
                except ImportError:
                    pass

            # Stage 6: Retrieval planning and execution
            retrieval_plan = plan_retrieval(
                message_text=run.intake.normalized_content,
                intent_primary=run.intent_result.get("primary", ""),
                project_preference=run.qualification.get("project_preference", ""),
            )
            run.retrieval_plan = {
            "query": retrieval_plan.query,
            "document_types": list(retrieval_plan.document_types),
            "chunk_types": list(retrieval_plan.chunk_types),
                "use_structured_pricing": retrieval_plan.use_structured_pricing,
            }

            retrieval_sources = []
            has_verified_pricing = False
            has_verified_availability = False
            try:
                from knowledge.retrieval import retrieve_by_query, get_structured_pricing, get_structured_availability
                results = retrieve_by_query(
                    retrieval_plan.query,
                    document_type=retrieval_plan.document_types[0] if retrieval_plan.document_types else None,
                    limit=retrieval_plan.limit,
                )
                retrieval_sources = [{"chunk_id": r.chunk_id, "document_title": r.document_title} for r in results[:5]]
                if retrieval_plan.use_structured_pricing and retrieval_plan.project_id:
                    pricing = get_structured_pricing(retrieval_plan.project_id)
                    if pricing and pricing.get("is_verified"):
                        has_verified_pricing = True
                    avail = get_structured_availability(retrieval_plan.project_id)
                    if avail and avail.get("is_verified"):
                        has_verified_availability = True
            except Exception as e:
                try:
                    from core.observability import log_exception
                    log_exception(component="orchestration", exc=e, stage="retrieval", run_id=run_id, conversation_id=conversation_id)
                except ImportError:
                    pass
                logger.warning("Retrieval failed: %s", e)
                run.retrieval_plan["retrieval_error"] = str(e)
                from core.resilience import get_fallback_for
                run.retrieval_plan["fallback_reason"] = "missing_knowledge" if "syntax" in str(e).lower() or "vector" in str(e).lower() else "structured_unavailable"
            run.retrieval_sources = retrieval_sources
            run.has_verified_pricing = has_verified_pricing
            run.has_verified_availability = has_verified_availability

            # Post-retrieval: set safe_response_policy and unavailable_data for guardrails
            intent_primary = (run.intent_result.get("primary") or "").lower()
            msg_lower = (run.intake.normalized_content or "").lower()
            is_price_inquiry = intent_primary_is_strict_price_inquiry(intent_primary)
            is_availability_inquiry = (
                "availability" in intent_primary or
                any(kw in msg_lower for kw in ("متوفر", "متبقى", "وحدة متبقية", "availability", "units left", "كم وحدة"))
            )
            if is_price_inquiry and not has_verified_pricing:
                run.routing["safe_response_policy"] = True
            if is_availability_inquiry and not has_verified_availability:
                run.routing["unavailable_data"] = True
            if run.retrieval_plan.get("retrieval_error") or run.retrieval_plan.get("fallback_reason"):
                run.routing["unavailable_data"] = True
            elif retrieval_plan.use_structured_pricing and not has_verified_pricing and is_price_inquiry:
                run.routing["unavailable_data"] = True  # Project fact requested but unavailable

            run.current_stage = PipelineStage.RETRIEVAL_PLANNING
            _log_stage(run, PipelineStage.RETRIEVAL_PLANNING, {"sources_count": len(retrieval_sources), "has_verified_pricing": has_verified_pricing})

            # Stage 7: Response drafting (sales/support/recommendation modes or generic LLM)
            draft = ""
            recommendation_matches = []

            if response_mode == "recommendation":
                from decimal import Decimal, InvalidOperation
                from engines.recommendation_engine import recommend_projects
                from engines.response_builder import build_recommendation_response
                qual = run.qualification
                budget_min, budget_max = None, None
                try:
                    if qual.get("budget_min"):
                        budget_min = Decimal(str(qual["budget_min"]))
                except (ValueError, TypeError, InvalidOperation):
                    budget_min = None
                try:
                    if qual.get("budget_max"):
                        budget_max = Decimal(str(qual["budget_max"]))
                except (ValueError, TypeError, InvalidOperation):
                    budget_max = None
                rec_result = recommend_projects(
                    budget_min=budget_min,
                    budget_max=budget_max,
                    location_preference=qual.get("location_preference", ""),
                    property_type=qual.get("property_type", ""),
                    purpose=qual.get("purpose", ""),
                    urgency=qual.get("urgency", ""),
                    limit=5,
                )
                matches = rec_result.matches
                recommendation_matches = [
                    {
                        "project_id": m.project_id,
                        "project_name": m.project_name,
                        "location": m.location,
                        "price_min": float(m.price_min) if m.price_min else None,
                        "price_max": float(m.price_max) if m.price_max else None,
                        "rationale": m.rationale,
                        "fit_score": m.fit_score,
                        "match_reasons": m.match_reasons,
                        "confidence": m.confidence,
                        "trade_offs": m.trade_offs,
                        "has_verified_pricing": m.has_verified_pricing,
                    }
                    for m in matches
                ]
                run.retrieval_sources = recommendation_matches
                run.recommendation_matches = recommendation_matches
                run.recommendation_result = {
                    "overall_confidence": rec_result.overall_confidence,
                    "alternatives": [
                        {"project_id": a.project_id, "project_name": a.project_name, "rationale": a.rationale}
                        for a in rec_result.alternatives
                    ],
                    "qualification_summary": rec_result.qualification_summary,
                    "data_completeness": rec_result.data_completeness,
                }
                draft = build_recommendation_response(matches, lang=lang or "ar")
                if matches:
                    try:
                        from core.observability import log_recommendation_generated
                        log_recommendation_generated(
                            match_count=len(matches),
                            run_id=run_id,
                            conversation_id=conversation_id,
                            customer_id=customer_id,
                        )
                    except ImportError:
                        pass
            elif response_mode == "sales":
                from engines.sales_engine import generate_sales_response
                hist = conversation_history or []
                retrieval_ctx = "\n\n".join([f"[{s.get('document_title', '')}]" for s in retrieval_sources[:3]]) if retrieval_sources else ""
                draft = generate_sales_response(
                    run.intake.normalized_content,
                    mode=sales_mode,
                    conversation_history=hist,
                    qualification=run.qualification,
                    retrieval_context=retrieval_ctx,
                    has_verified_pricing=has_verified_pricing,
                    use_llm=use_llm,
                    channel=channel,
                )
            elif response_mode == "support" or _is_support_routing(run):
                from engines.support_engine import generate_support_response
                hist = conversation_history or []
                support_cat = support_category or run.qualification.get("support_category", "") or run.routing.get("queue", "")
                draft = generate_support_response(
                    run.intake.normalized_content,
                    mode="angry_customer" if (is_angry or run.routing.get("escalation_ready")) else "existing_customer_support",
                    category=support_cat,
                    is_angry=is_angry,
                    conversation_history=hist,
                    use_llm=use_llm,
                    channel=channel,
                )
            else:
                try:
                    from core.adapters.llm import get_llm_client
                    client = get_llm_client()
                    context = "\n\n".join([f"[{s.get('document_title','')}]" for s in retrieval_sources[:3]]) if retrieval_sources else ""
                    safe_instruction = ""
                    if run.routing.get("safe_response_policy") or run.routing.get("unavailable_data"):
                        safe_instruction = " Do NOT state exact prices, unit counts, or availability unless from verified structured data. Suggest contacting the team for specifics."
                    messages = [
                        {"role": "system", "content": f"You are a real estate assistant. Context: {context[:500]}. Be helpful and professional.{safe_instruction}"},
                        {"role": "user", "content": run.intake.normalized_content},
                    ]
                    draft = client.chat_completion(messages, timeout=llm_timeout_seconds)
                except Exception as e:
                    try:
                        from core.observability import log_exception
                        log_exception(component="orchestration", exc=e, stage="response_drafting", run_id=run_id, conversation_id=conversation_id)
                    except ImportError:
                        pass
                    logger.warning("Response drafting failed: %s", e)
                    from core.resilience import get_fallback_for
                    is_timeout = "timeout" in str(e).lower() or "timed out" in str(e).lower()
                    draft = get_fallback_for("llm_timeout" if is_timeout else "generic")

            run.draft_response = draft or ""

            run.current_stage = PipelineStage.RESPONSE_DRAFTING
            _log_stage(run, PipelineStage.RESPONSE_DRAFTING, {"draft_length": len(draft)})

        # Stage 8: Policy/guardrail check
        policy = apply_policy_engine(
            draft,
            has_verified_pricing=has_verified_pricing,
            has_verified_availability=has_verified_availability,
            routing=run.routing,
            intent=run.intent_result,
            customer_type=run.routing.get("customer_type", "new_lead"),
            requires_clarification=intel.requires_clarification,
            user_message=run.intake.normalized_content or "",
            conversation_history=conversation_history,
        )
        run.policy_decision = {
            "allow_response": policy.allow_response,
            "rewrite_to_safe": policy.rewrite_to_safe,
            "force_escalation": policy.force_escalation,
            "request_clarification": policy.request_clarification,
            "applied_policy": policy.applied_policy.value if hasattr(policy.applied_policy, "value") else str(policy.applied_policy),
            "violations": [v.value for v in policy.violations],
            "block_reason": policy.block_reason or "",
            "safe_response_used": bool(policy.safe_rewrite),
        }

        if policy.rewrite_to_safe and policy.safe_rewrite:
            run.final_response = policy.safe_rewrite
        elif not policy.allow_response and policy.safe_rewrite:
            run.final_response = policy.safe_rewrite
        else:
            run.final_response = draft

        if policy.safe_rewrite and (
            run.routing.get("safe_response_policy") or run.routing.get("unavailable_data")
        ):
            try:
                from core.observability import log_unverified_fact_blocked
                intent_hint = (run.intent_result.get("primary") or "").lower()
                block_reason = "pricing" if "price" in intent_hint else "availability" if "availability" in intent_hint or "متوفر" in (run.intake.normalized_content or "") else "unverified_data"
                log_unverified_fact_blocked(
                    block_reason=block_reason,
                    intent_hint=intent_hint or "-",
                    run_id=run_id,
                    conversation_id=conversation_id,
                )
            except ImportError:
                pass

        if policy.force_escalation:
            run.escalation_flags.append("policy_forced_escalation")

        run.current_stage = PipelineStage.POLICY_GUARDRAIL_CHECK
        _log_stage(run, PipelineStage.POLICY_GUARDRAIL_CHECK, run.policy_decision)

        # Stage 9: Action execution (determine actions; actual side effects are optional)
        next_act = compute_next_best_action(
            customer_type=run.routing.get("customer_type", "new_lead"),
            intent_primary=run.intent_result.get("primary", ""),
            missing_fields=run.qualification.get("missing_fields", []),
            score=run.scoring.get("score", 0),
            temperature=run.scoring.get("temperature", ""),
            routing=run.routing,
            requires_clarification=intel.requires_clarification,
            journey_stage=run.journey_stage,
        )
        next_act_val = next_act.action.value if hasattr(next_act.action, "value") else str(next_act.action)
        run.actions_triggered = [
            {"action": next_act_val, "reason": next_act.reason}
        ]
        try:
            from core.observability import log_next_best_action_selected
            log_next_best_action_selected(
                action=next_act_val,
                reason=next_act.reason or "",
                run_id=run_id,
                conversation_id=conversation_id,
            )
        except ImportError:
            pass

        # Risk notes for handoff
        risk_notes = []
        if run.routing.get("quarantine"):
            risk_notes.append("Spam/quarantine")
        if policy.violations:
            risk_notes.extend([f"Guardrail: {v.value}" for v in policy.violations])
        if run.routing.get("escalation_ready"):
            risk_notes.append("Escalation ready")

        run.handoff_summary = build_handoff_summary(
            customer_type=run.routing.get("customer_type", "new_lead"),
            intent=run.intent_result,
            qualification=run.qualification,
            scoring=run.scoring,
            routing=run.routing,
            next_action={"action": next_act.action.value if hasattr(next_act.action, "value") else str(next_act.action), "reason": next_act.reason},
            risk_notes=risk_notes,
        )

        run.current_stage = PipelineStage.ACTION_EXECUTION
        _log_stage(run, PipelineStage.ACTION_EXECUTION, {"actions": run.actions_triggered})

        # Stage 10: Audit logging (final)
        run.status = RunStatus.ESCALATED if run.escalation_flags else RunStatus.COMPLETED
        run.current_stage = PipelineStage.COMPLETED

        log(
            action="orchestration_completed",
            actor=external_id or "system",
            subject_type="orchestration_run",
            subject_id=run_id,
            payload={
                "status": run.status.value,
                "score": run.scoring.get("score"),
                "policy_applied": run.policy_decision.get("applied_policy"),
                "actions": run.actions_triggered,
            },
            run_id=run_id,
            conversation_id=conversation_id,
        )
        try:
            from core.observability import log_orchestration_complete
            log_orchestration_complete(
                run_id=run_id,
                status=run.status.value,
                route=run.routing.get("route", ""),
                temperature=run.scoring.get("temperature", ""),
            )
        except ImportError:
            pass

        # Save snapshot for operator console when conversation_id provided
        if conversation_id:
            try:
                from conversations.models import Conversation
                from console.models import OrchestrationSnapshot
                conv = Conversation.objects.filter(pk=conversation_id).first()
                if conv:
                    user_msg = None
                    if message_id:
                        from conversations.models import Message
                        user_msg = Message.objects.filter(pk=message_id, conversation=conv).first()
                    if not user_msg:
                        user_msg = conv.messages.filter(role="user").order_by("-created_at").first()
                    esc_flag = bool(run.escalation_flags or run.routing.get("escalation_ready"))
                    next_act_val = run.actions_triggered[0] if run.actions_triggered else {}
                    next_action_str = f"{next_act_val.get('action', '')}: {next_act_val.get('reason', '')}" if next_act_val else ""
                    OrchestrationSnapshot.objects.create(
                        conversation=conv,
                        message=user_msg,
                        run_id=run_id,
                        intent=run.intent_result,
                        qualification=run.qualification,
                        scoring=run.scoring,
                        routing=run.routing,
                        retrieval_sources=run.retrieval_sources,
                        policy_decision=run.policy_decision,
                        actions_triggered=run.actions_triggered,
                        next_best_action=next_action_str or run.scoring.get("next_best_action", ""),
                        response_produced=run.final_response,
                        customer_type=run.routing.get("customer_type", ""),
                        mode=response_mode or "generic",
                        source_channel=run.intake.channel if run.intake else "web",
                        escalation_flag=esc_flag,
                        journey_stage=run.journey_stage,
                    )
            except Exception as snap_err:
                try:
                    from core.observability import log_exception
                    log_exception(component="orchestration", exc=snap_err, stage="snapshot", run_id=run_id, conversation_id=conversation_id)
                except ImportError:
                    pass
                logger.warning("Failed to save orchestration snapshot: %s", snap_err)

            # CRM sync: conversation outcomes -> CRM record (adapter-friendly for first company)
            if conv and conv.customer_id and getattr(settings, "CRM_SYNC_ENABLED", True):
                try:
                    from crm.services.sync_service import sync_conversation_outcome
                    note_parts = []
                    if run.scoring:
                        note_parts.append(f"Score: {run.scoring.get('score')} ({run.scoring.get('temperature', '')})")
                    if run.qualification:
                        q = run.qualification
                        if q.get("budget_min") or q.get("budget_max"):
                            note_parts.append(f"Budget: {q.get('budget_min')}-{q.get('budget_max')}")
                        if q.get("project_preference"):
                            note_parts.append(f"Project: {q.get('project_preference')}")
                    if note_parts:
                        sync_conversation_outcome(
                            conv.customer_id,
                            note=" | ".join(note_parts),
                            lead_stage=run.journey_stage or "",
                            actor="orchestrator",
                        )
                except Exception as sync_err:
                    try:
                        from core.observability import log_exception
                        log_exception(component="crm_sync", exc=sync_err, stage="orchestrator_sync", run_id=run_id, conversation_id=conversation_id, customer_id=conv.customer_id if conv else None)
                    except ImportError:
                        pass
                    logger.warning("CRM sync failed: %s", sync_err)

    except Exception as e:
        try:
            from core.observability import log_exception, log_orchestration_failed
            log_exception(component="orchestration", exc=e, stage="unknown", run_id=run_id, conversation_id=conversation_id)
            log_orchestration_failed(run_id=run_id, reason=str(e), stage="unknown")
        except ImportError:
            pass
        logger.exception("Orchestration failed: %s", e)
        run.status = RunStatus.FAILED
        run.failure_reason = str(e)
        run.current_stage = PipelineStage.FAILED
        try:
            from audit.service import log
            log(
                action="orchestration_failed",
                actor=external_id or "system",
                subject_type="orchestration_run",
                subject_id=run_id,
                payload={"reason": str(e)},
                run_id=run_id,
                conversation_id=conversation_id,
            )
        except Exception:
            pass
        try:
            from core.observability import log_orchestration_failed
            log_orchestration_failed(run_id=run_id, reason=str(e), stage="unknown")
        except ImportError:
            pass

    return run
