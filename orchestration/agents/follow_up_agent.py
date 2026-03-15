"""
Follow-up Agent - generates smart follow-up messages for dormant leads.
Runs standalone (not in conversation pipeline). Uses follow_up_input for lead context.
Stores recommendations as structured records. Never auto-sends unless system policy enables.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import FollowUpAgentOutput
from engines.follow_up_engine import generate_follow_up_recommendations


class FollowUpAgent:
    name = "follow_up"

    def run(self, context: AgentContext) -> AgentResult:
        """
        Generate follow-up recommendations from follow_up_input.
        Returns structured records; does NOT send. auto_send_enabled stays False.
        """
        try:
            inp = context.follow_up_input or {}
            buyer_stage = inp.get("buyer_stage", "")
            lead_score = int(inp.get("lead_score", 0) or 0)
            last_projects = inp.get("last_discussed_projects") or inp.get("last_projects") or []
            time_since = float(inp.get("time_since_last_interaction_hours", 0) or 0)
            lead_ref = inp.get("lead_ref", "") or str(context.customer_id or context.external_id or "")
            lang = context.lang or "ar"

            if not isinstance(last_projects, list):
                last_projects = list(last_projects) if last_projects else []

            recs = generate_follow_up_recommendations(
                buyer_stage=buyer_stage,
                lead_score=lead_score,
                last_discussed_projects=last_projects,
                time_since_last_interaction_hours=time_since,
                lead_ref=lead_ref,
                lang=lang,
            )
            recommendations = [r.to_dict() for r in recs]

            output = FollowUpAgentOutput(
                recommendations=recommendations,
                auto_send_enabled=False,  # Never enable by default; system policy decides
                lead_ref=lead_ref,
            )
            context.follow_up_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "recommendation_count": len(recommendations),
                    "follow_up_type": recommendations[0].get("type", "") if recommendations else "",
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
