"""
Persist orchestration run outputs to domain models: LeadScore, LeadQualification,
Recommendation, SupportCase, Escalation. Single persistence path, no parallel systems.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional

from orchestration.schemas import OrchestrationRun


def _is_lead_type(customer_type: str) -> bool:
    """True if customer is a lead (not support/spam)."""
    ct = (customer_type or "").lower()
    return ct in ("new_lead", "returning_lead", "broker", "existing_customer")


def _is_support_type(customer_type: str) -> bool:
    ct = (customer_type or "").lower()
    return ct in ("support_customer", "existing_customer")


def _temperature_to_stage(temperature: str) -> str:
    """Map temperature to buyer journey stage (fallback when journey_stage not available)."""
    t = (temperature or "").lower()
    if t == "hot":
        return "visit_planning"
    if t == "warm":
        return "consideration"
    if t in ("cold", "nurture", "unqualified"):
        return "awareness"
    if t == "spam":
        return "unknown"
    return "unknown"


def _confidence_float_to_level(conf: float) -> str:
    if conf >= 0.7:
        return "high"
    if conf >= 0.5:
        return "medium"
    if conf > 0:
        return "low"
    return "unknown"


def _sync_orchestration_outcome_to_crm(
    run: OrchestrationRun,
    customer_id: int,
    customer_type: str,
    scoring: dict,
    is_support_route: bool,
    intent_primary: str,
) -> None:
    """Push conversation outcomes to CRM. Note, stage, tags from orchestration run."""
    if not _is_lead_type(customer_type) and not _is_support_type(customer_type):
        return

    from crm.services.sync_service import sync_conversation_outcome

    note_parts = []
    if run.intake and run.intake.normalized_content:
        note_parts.append(f"Intent: {intent_primary or 'general'}. Message: {run.intake.normalized_content[:300]}")
    if run.final_response:
        note_parts.append(f"AI: {run.final_response[:300]}")
    note = " | ".join(note_parts) if note_parts else None

    lead_stage = None
    tags_add = []
    if _is_lead_type(customer_type) and scoring:
        temp = scoring.get("temperature", "")
        stage = getattr(run, "journey_stage", "") or _temperature_to_stage(temp)
        lead_stage = stage
        if temp:
            tags_add.append(f"{temp}_lead")

    if is_support_route:
        tags_add.append("support_touch")

    sync_conversation_outcome(
        customer_id,
        note=note,
        lead_stage=lead_stage,
        tags_add=tags_add if tags_add else None,
        actor="ai_system",
    )


def persist_orchestration_artifacts(
    run: OrchestrationRun,
    customer_id: int,
    conversation_id: int,
    user_message_id: int,
    *,
    mode: str = "",
    source_channel: str = "web",
    is_angry: bool = False,
) -> None:
    """
    Persist run outputs to LeadScore, LeadQualification, Recommendation, SupportCase, Escalation.
    """
    from leads.models import Customer, LeadScore, LeadQualification, LeadProfile
    from recommendations.models import Recommendation
    from support.models import SupportCase, Escalation
    from core.enums import LeadTemperature, BuyerJourneyStage, EscalationReason, EscalationStatus

    customer_type = run.routing.get("customer_type", "")
    scoring = run.scoring or {}
    qualification = run.qualification or {}
    routing = run.routing or {}

    # LeadScore - for lead-type customers
    if _is_lead_type(customer_type) and scoring.get("score") is not None:
        score_val = scoring.get("score", 0)
        temp = scoring.get("temperature", "nurture")
        temp_choice = next((t for t in LeadTemperature if t.value == temp), LeadTemperature.NURTURE)
        # Prefer run.journey_stage from pipeline; fallback to temperature mapping
        stage = getattr(run, "journey_stage", "") or _temperature_to_stage(temp)
        valid_stages = [c[0] for c in BuyerJourneyStage.choices]
        stage_choice = next((s for s in BuyerJourneyStage if s.value == stage), BuyerJourneyStage.UNKNOWN)
        stage_val = stage if stage in valid_stages else _temperature_to_stage(temp)
        reason_codes = scoring.get("reason_codes", [])
        explanation = [
            {"factor": r.get("factor", ""), "contribution": r.get("contribution", 0), "note": r.get("note", "")}
            for r in reason_codes
        ]
        next_act = (run.actions_triggered or [{}])[0] if run.actions_triggered else {}
        next_action_str = f"{next_act.get('action', '')}: {next_act.get('reason', '')}".strip(": ").strip()
        if not next_action_str and scoring.get("next_best_action"):
            next_action_str = scoring.get("next_best_action", "")[:255]
        LeadScore.objects.create(
            customer_id=customer_id,
            score=score_val,
            temperature=temp_choice.value if hasattr(temp_choice, "value") else temp,
            journey_stage=stage_val,
            next_best_action=next_action_str[:255] if next_action_str else "",
            explanation=explanation,
        )
        try:
            from core.observability import log_scoring, log_lead_temperature_assigned
            log_scoring(customer_id=customer_id, score=score_val, temperature=temp)
            log_lead_temperature_assigned(customer_id=customer_id, temperature=temp, score=score_val)
        except ImportError:
            pass

    # LeadQualification - for lead-type when we have qualification data
    if _is_lead_type(customer_type) and qualification:
        budget_min = qualification.get("budget_min")
        budget_max = qualification.get("budget_max")
        if budget_min is not None:
            try:
                budget_min = Decimal(str(budget_min))
            except (TypeError, ValueError, InvalidOperation):
                budget_min = None
        if budget_max is not None:
            try:
                budget_max = Decimal(str(budget_max))
            except (TypeError, ValueError, InvalidOperation):
                budget_max = None
        loc = qualification.get("location_preference", "")
        prop = qualification.get("property_type", "")
        if budget_min or budget_max or loc or prop:
            LeadQualification.objects.create(
                customer_id=customer_id,
                conversation_id=conversation_id,
                message_id=user_message_id,
                budget_min=budget_min,
                budget_max=budget_max,
                location_preference=loc or "",
                property_type=prop or "",
                confidence=qualification.get("confidence", "unknown"),
                raw_extraction=qualification,
            )

    # LeadProfile / project interest - from qualification
    if _is_lead_type(customer_type) and qualification.get("project_preference"):
        LeadProfile.objects.create(
            customer_id=customer_id,
            source_channel=source_channel or "web",
            project_interest=qualification.get("project_preference", ""),
            metadata={},
        )

    # Recommendation - when we have recommendation matches
    if run.recommendation_matches:
        for rank, m in enumerate(run.recommendation_matches, 1):
            pid = m.get("project_id")
            if pid:
                Recommendation.objects.create(
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    project_id=pid,
                    rationale=m.get("rationale", ""),
                    rank=rank,
                    metadata=m,
                )
        try:
            from core.observability import log_recommendation
            log_recommendation(
                customer_id=customer_id,
                conversation_id=conversation_id,
                match_count=len(run.recommendation_matches),
            )
        except ImportError:
            pass

    # Escalation and SupportCase creation
    from leads.models import Customer
    from conversations.models import Conversation
    from orchestration.escalation_policy import resolve_escalation_reason
    from orchestration.handoff import enrich_handoff_with_identity

    cust = Customer.objects.filter(pk=customer_id).select_related("identity").first()
    conv = Conversation.objects.filter(pk=conversation_id).first()

    should_escalate = bool(
        run.escalation_flags or routing.get("escalation_ready") or routing.get("requires_human_review")
    )
    route = routing.get("route", "")
    is_support_route = route in ("support", "support_escalation", "legal_handoff")
    intent_primary = (run.intent_result or {}).get("primary", "")
    support_cat_from_qual = qualification.get("support_category", "")
    policy = run.policy_decision or {}

    # Build handoff summary (enriched with identity when we have customer/conversation)
    handoff = run.handoff_summary or {}
    handoff = enrich_handoff_with_identity(handoff, cust, conv)
    handoff["run_id"] = run.run_id
    handoff["last_message"] = run.intake.normalized_content[:300] if run.intake else ""

    escalation_obj = None
    if should_escalate and cust:
        reason = resolve_escalation_reason(
            is_angry=is_angry,
            intent_primary=intent_primary,
            routing_route=route,
            routing_safe_response_policy=routing.get("safe_response_policy", False),
            routing_requires_human_review=routing.get("requires_human_review", False),
            policy_forced_escalation=policy.get("force_escalation", False),
            policy_violations=policy.get("violations", []),
            has_verified_pricing=run.has_verified_pricing,
            intent_is_price_inquiry=intent_primary in ("price_inquiry", "pricing"),
            is_vip=bool(cust.metadata.get("vip") if getattr(cust, "metadata", None) else False),
            escalation_flags=run.escalation_flags,
        )
        escalation_obj = Escalation.objects.create(
            customer=cust,
            conversation=conv,
            reason=reason.value if hasattr(reason, "value") else reason,
            status=EscalationStatus.OPEN,
            notes=f"run_id={run.run_id} flags={run.escalation_flags}",
            handoff_summary=handoff,
        )
        try:
            from core.observability import log_escalation_triggered
            log_escalation_triggered(
                escalation_id=escalation_obj.id,
                customer_id=customer_id,
                reason=reason.value if hasattr(reason, "value") else str(reason),
            )
        except ImportError:
            pass

    # SupportCase - when routing indicates support
    if is_support_route:
        from support.triage import triage_support
        from core.enums import SupportCategory, SupportStatus

        triage = triage_support(
            intent_primary=intent_primary,
            support_category=support_cat_from_qual,
            is_angry=is_angry,
            routing_route=route,
            routing_escalation_ready=routing.get("escalation_ready", False),
        )
        valid_cats = [c[0] for c in SupportCategory.choices]
        category = triage.category if triage.category in valid_cats else "general_support"

        support_case = SupportCase.objects.create(
            customer=cust,
            conversation=conv,
            message_id=user_message_id,
            escalation=escalation_obj,
            category=category,
            summary=run.intake.normalized_content[:500] if run.intake else "",
            status=SupportStatus.OPEN.value,
            severity=triage.severity,
            sla_bucket=triage.sla_bucket,
            assigned_queue=triage.assigned_queue,
            escalation_trigger=triage.escalation_trigger,
            metadata={"run_id": run.run_id, "intent": intent_primary},
        )
        try:
            from core.observability import log_support_case_created, log_support_severity_assigned
            log_support_case_created(
                case_id=support_case.id,
                customer_id=customer_id,
                category=category,
            )
            log_support_severity_assigned(
                case_id=support_case.id,
                severity=triage.severity,
                category=category,
            )
        except ImportError:
            pass
        # Link support case to CRM for operator visibility
        try:
            from crm.services.sync_service import link_support_case
            link_support_case(customer_id=customer_id, support_case_id=support_case.id, actor="ai_system")
        except Exception as e:
            try:
                from core.observability import log_exception
                log_exception(component="crm_support_link", exc=e, stage="link_support_case", customer_id=customer_id, support_case_id=support_case.id)
            except ImportError:
                import logging
                logging.getLogger(__name__).warning("CRM support link failed: %s", e)

    # Sync meaningful outcomes to CRM (note, stage, tags)
    try:
        _sync_orchestration_outcome_to_crm(
            run=run,
            customer_id=customer_id,
            customer_type=customer_type,
            scoring=scoring,
            is_support_route=is_support_route,
            intent_primary=intent_primary,
        )
    except Exception as e:
        try:
            from core.observability import log_exception
            log_exception(component="crm_sync", exc=e, stage="sync_orchestration_outcome_to_crm", customer_id=customer_id, customer_type=customer_type, is_support_route=is_support_route)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning("CRM sync failed: %s", e)
