"""
Buyer Journey Stage Agent - detects where the customer is in the buying journey.
Uses current message + memory + conversation history + intent + qualification.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import JourneyStageAgentOutput
from orchestration.journey_stage import detect_journey_stage


def _next_sales_move_for_stage(stage: str, qualification: dict, intent_primary: str) -> str:
    """Suggest next sales move based on stage."""
    stage = (stage or "").lower()
    has_budget = bool(qualification.get("budget_min") or qualification.get("budget_max"))
    has_location = bool(qualification.get("location_preference"))
    has_project = bool(qualification.get("project_preference"))

    moves = {
        "awareness": "Share value proposition and qualify budget/location" if not (has_budget or has_location) else "Gather project preference",
        "exploration": "Offer property overviews and narrow preferences",
        "consideration": "Send project details and schedule visit",
        "shortlisting": "Share brochures and arrange site visit",
        "visit_planning": "Confirm visit slot and send directions",
        "negotiation": "Present offers and facilitate decision",
        "booking": "Guide through booking steps and documentation",
        "post_booking": "Follow up on handover and satisfaction",
        "support": "Resolve issue and maintain relationship",
        "support_retention": "Resolve issue and maintain relationship",
    }
    return moves.get(stage, "Continue qualification and nurture")


class JourneyStageAgent:
    name = "journey_stage"

    def run(self, context: AgentContext) -> AgentResult:
        """Detect journey stage from message, memory, conversation history."""
        try:
            intent_data = context.intent_output or {}
            qualification_data = context.get_qualification()
            memory = context.memory_output or {}
            # routing from sales_strategy (pipeline runs journey_stage after sales_strategy)
            routing = getattr(context, "routing_output", None) or {}
            prior_stage = memory.get("journey_stage", "") or ""

            intent_primary = intent_data.get("primary", "")
            customer_type = memory.get("customer_type_hint", "new_lead")
            temperature = ""
            score = 0
            if qualification_data.get("lead_temperature"):
                temperature = str(qualification_data.get("lead_temperature", ""))
            if qualification_data.get("lead_score") is not None:
                score = int(qualification_data.get("lead_score", 0))

            has_budget = bool(qualification_data.get("budget_min") or qualification_data.get("budget_max"))
            has_location = bool(qualification_data.get("location_preference"))
            has_project = bool(qualification_data.get("project_preference"))

            stage_val = detect_journey_stage(
                intent_primary=intent_primary,
                customer_type=customer_type,
                temperature=temperature,
                score=score,
                qualification=qualification_data,
                routing_route=routing.get("route", ""),
                prior_stage=prior_stage,
                has_project_preference=has_project,
                has_budget=has_budget,
                has_location=has_location,
            )

            # Build reasoning from context
            reasons = []
            if intent_primary:
                reasons.append(f"intent={intent_primary}")
            if customer_type:
                reasons.append(f"customer_type={customer_type}")
            if temperature:
                reasons.append(f"temperature={temperature}")
            if has_budget or has_location or has_project:
                qual_parts = []
                if has_budget:
                    qual_parts.append("budget")
                if has_location:
                    qual_parts.append("location")
                if has_project:
                    qual_parts.append("project")
                reasons.append(f"qualified: {', '.join(qual_parts)}")
            if prior_stage and prior_stage != stage_val:
                reasons.append(f"prior_stage={prior_stage}")

            # Confidence: higher when we have strong signals
            confidence = 0.6
            if intent_primary and customer_type:
                confidence = 0.75
            if (has_budget or has_location) and intent_primary:
                confidence = 0.85
            if temperature == "hot" or score >= 75:
                confidence = 0.9

            next_move = _next_sales_move_for_stage(stage_val, qualification_data, intent_primary)

            output = JourneyStageAgentOutput(
                stage=stage_val,
                confidence=confidence,
                stage_reasoning=reasons[:5],
                next_sales_move=next_move,
            )
            context.journey_stage_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={"stage": stage_val, "confidence": confidence},
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
