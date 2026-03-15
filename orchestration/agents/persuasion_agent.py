"""
Persuasion and Objection Handling Agent.
Helps the AI respond like a smart sales consultant—handles hesitation,
uses ethical persuasion, avoids pressure and false urgency.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import PersuasionAgentOutput
from engines.persuasion import (
    detect_objection_type,
    get_persuasion_output,
    map_legacy_objection_to_type,
)
from engines.objection_library import detect_objection as legacy_detect_objection


class PersuasionAgent:
    name = "persuasion"

    def run(self, context: AgentContext) -> AgentResult:
        """Detect objection, compute ethical persuasion output."""
        try:
            msg = (context.message_text or "").strip()
            if not msg:
                context.persuasion_output = PersuasionAgentOutput().to_dict()
                return AgentResult(agent_name=self.name, success=True, metadata={"objection": None})

            # Prefer our detection (covers comparing_projects, delivery_concerns, etc.)
            objection_type = detect_objection_type(msg)
            if not objection_type:
                # Fallback to legacy objection_library
                legacy_key = legacy_detect_objection(msg)
                if legacy_key:
                    objection_type = map_legacy_objection_to_type(legacy_key)
            if not objection_type:
                # Also check sales_strategy output (runs before us in pipeline)
                strategy = context.sales_strategy_output or {}
                legacy_key = strategy.get("objection_key")
                if legacy_key:
                    objection_type = map_legacy_objection_to_type(legacy_key)

            if not objection_type:
                context.persuasion_output = PersuasionAgentOutput().to_dict()
                return AgentResult(agent_name=self.name, success=True, metadata={"objection": None})

            po = get_persuasion_output(objection_type)
            output = PersuasionAgentOutput(
                objection_type=po.objection_type,
                handling_strategy=po.handling_strategy,
                persuasive_points=po.persuasive_points,
                preferred_cta=po.preferred_cta,
            )
            context.persuasion_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "objection_type": objection_type,
                    "handling_strategy": po.handling_strategy,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
