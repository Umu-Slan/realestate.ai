"""
Lead Qualification Agent - extracts qualification and scores lead quality.
Uses 9 structured signals: budget/location/property clarity, urgency,
engagement, returning behavior, visit interest, financing readiness, decision authority.
Deterministic, explainable. Persists via orchestration persistence layer.
"""
from decimal import Decimal

from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import LeadQualificationAgentOutput
from orchestration.agents.lead_qualification_scorer import (
    compute_lead_qualification_score,
    LeadQualificationScore,
)


def _extraction_to_qualification_dict(result) -> dict:
    """Convert QualificationExtraction to dict for scorer."""
    return {
        "budget_min": result.budget_min,
        "budget_max": result.budget_max,
        "budget_clarity": getattr(result, "budget_clarity", "") or "",
        "location_preference": (result.location_preference or "").strip(),
        "project_preference": (result.project_preference or "").strip(),
        "property_type": (result.property_type or "").strip(),
        "purpose": getattr(result, "residence_vs_investment", "") or "",
        "urgency": (result.urgency or "").strip(),
        "purchase_timeline": getattr(result, "purchase_timeline", "") or "",
        "financing_readiness": getattr(result, "financing_readiness", "") or "",
        "payment_method": getattr(result, "payment_method", "") or "",
        "missing_fields": list(result.missing_fields or []),
        "confidence": result.confidence or "unknown",
    }


def _merge_prior_qualification(qualification: dict, customer_id: int | None, conversation_id: int | None) -> dict:
    """Merge prior LeadQualification from DB so we never lose budget/location across turns."""
    if not customer_id:
        return qualification
    try:
        from leads.models import LeadQualification
        qs = LeadQualification.objects.filter(customer_id=customer_id).order_by("-created_at")
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        prior = qs.first()
        if not prior:
            return qualification
        out = dict(qualification)
        if (not out.get("budget_min") and not out.get("budget_max")) and (prior.budget_min or prior.budget_max):
            if prior.budget_min:
                out["budget_min"] = prior.budget_min
            if prior.budget_max:
                out["budget_max"] = prior.budget_max
        if not out.get("location_preference") and prior.location_preference:
            out["location_preference"] = prior.location_preference
        if not out.get("property_type") and prior.property_type:
            out["property_type"] = prior.property_type
        # Recompute missing_fields: only fields we still lack
        missing = []
        if not out.get("budget_min") and not out.get("budget_max"):
            missing.append("budget")
        if not out.get("location_preference"):
            missing.append("location")
        if not out.get("project_preference"):
            missing.append("project")
        if not out.get("property_type"):
            missing.append("property_type")
        out["missing_fields"] = missing
        return out
    except Exception:
        return qualification


def _merge_intent_entities_into_qualification(qualification: dict, intent_entities: dict) -> dict:
    """Merge intent entities into qualification (intent can fill gaps)."""
    q = dict(qualification)
    if not intent_entities:
        return q
    if intent_entities.get("budget") and not (q.get("budget_min") or q.get("budget_max")):
        b = intent_entities["budget"]
        if isinstance(b, dict):
            q["budget_min"] = b.get("min")
            q["budget_max"] = b.get("max")
    if intent_entities.get("location") and not q.get("location_preference"):
        q["location_preference"] = intent_entities["location"]
    if intent_entities.get("property_type") and not q.get("property_type"):
        q["property_type"] = intent_entities["property_type"]
    if intent_entities.get("timeline") and not q.get("urgency"):
        q["urgency"] = intent_entities["timeline"]
    if intent_entities.get("investment_vs_residence") and not q.get("purpose"):
        q["purpose"] = intent_entities["investment_vs_residence"]
    if intent_entities.get("bedrooms") is not None and q.get("bedrooms") is None:
        q["bedrooms"] = intent_entities["bedrooms"]
    return q


class LeadQualificationAgent:
    name = "lead_qualification"

    def run(self, context: AgentContext) -> AgentResult:
        """Extract qualification, compute lead score, output structured result."""
        try:
            intent = context.intent_output or {}
            if intent.get("is_spam"):
                score_result = compute_lead_qualification_score(
                    {}, intent, is_spam=True,
                )
                output = LeadQualificationAgentOutput(
                    missing_fields=[],
                    lead_score=score_result.lead_score,
                    lead_temperature=score_result.lead_temperature,
                    reasoning=[{"factor": r.factor, "contribution": r.contribution, "note": r.note} for r in score_result.reasoning],
                    next_best_action=score_result.next_best_action,
                )
                context.qualification_output = output.to_dict()
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    metadata={"skipped": "spam"},
                )

            from intelligence.services.qualification_extractor import extract_qualification

            result = extract_qualification(
                context.message_text,
                conversation_history=context.conversation_history or [],
                use_llm=context.use_llm,
            )

            qualification = _extraction_to_qualification_dict(result)
            intent_entities = intent.get("entities") or {}
            qualification = _merge_intent_entities_into_qualification(qualification, intent_entities)

            # Merge prior qualification from DB - never lose budget/location across turns
            qualification = _merge_prior_qualification(qualification, context.customer_id, context.conversation_id)

            identity = context.identity_resolution or {}
            memory_profile = {}
            try:
                from orchestration.agents.memory_store import load_customer_profile
                prior = load_customer_profile(
                    customer_id=context.customer_id,
                    identity_id=identity.get("identity_id"),
                )
                memory_profile = prior.to_dict()
            except Exception:
                pass

            message_count = len(context.conversation_history or []) + 1
            customer_type = "returning_lead" if identity.get("matched") else "new_lead"
            if context.response_mode == "support":
                customer_type = "support_customer"

            score_result = compute_lead_qualification_score(
                qualification=qualification,
                intent_output=intent,
                message_count=message_count,
                customer_type_hint=customer_type,
                identity_matched=identity.get("matched", False),
                memory_profile=memory_profile,
                message_text=context.message_text or "",
                is_spam=False,
                is_broker=intent.get("is_broker", False),
            )

            # CRITICAL: Output MERGED qualification (never raw extraction) so downstream
            # agents receive persisted budget/location across turns.
            output = LeadQualificationAgentOutput(
                budget_min=qualification.get("budget_min") or result.budget_min,
                budget_max=qualification.get("budget_max") or result.budget_max,
                location_preference=(qualification.get("location_preference") or result.location_preference or "").strip(),
                project_preference=(qualification.get("project_preference") or result.project_preference or "").strip(),
                property_type=(qualification.get("property_type") or result.property_type or "").strip(),
                purpose=(qualification.get("purpose") or result.residence_vs_investment or "").strip(),
                urgency=(qualification.get("urgency") or result.urgency or "").strip(),
                bedrooms=qualification.get("bedrooms"),
                missing_fields=score_result.missing_fields,
                confidence=qualification.get("confidence") or result.confidence or "unknown",
                lead_score=score_result.lead_score,
                lead_temperature=score_result.lead_temperature,
                reasoning=[{"factor": r.factor, "contribution": r.contribution, "note": r.note} for r in score_result.reasoning],
                next_best_action=score_result.next_best_action,
            )
            context.qualification_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "confidence": output.confidence,
                    "lead_score": output.lead_score,
                    "lead_temperature": output.lead_temperature,
                    "missing_count": len(output.missing_fields),
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
