"""
Intent Agent - classifies user intent from message and history.
Uses production-grade intent detector: Arabic-first, entity extraction, stage hints.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import IntentAgentOutput
from orchestration.agents.intent_detector import detect_intent


class IntentAgent:
    name = "intent"

    def run(self, context: AgentContext) -> AgentResult:
        """Classify intent from message with entity extraction and stage hint."""
        try:
            customer_type_hint = ""
            if context.response_mode == "support":
                customer_type_hint = "support_customer"
            elif context.response_mode == "recommendation":
                customer_type_hint = "new_lead"
            elif context.identity_resolution.get("matched"):
                customer_type_hint = "existing_customer"

            result = detect_intent(
                context.message_text,
                conversation_history=context.conversation_history or [],
                customer_type=customer_type_hint,
                use_llm=context.use_llm,
            )

            output = IntentAgentOutput(
                primary=result.legacy_primary,
                secondary=[],
                confidence=result.confidence,
                is_support=result.is_support,
                is_spam=result.is_spam,
                is_broker=result.is_broker,
                sales_intent=result.intent,
                entities=result.extracted_entities,
                stage_hint=result.stage_hint,
            )
            context.intent_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "intent": result.intent,
                    "sales_intent": result.intent,
                    "confidence": output.confidence,
                    "stage_hint": result.stage_hint,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
