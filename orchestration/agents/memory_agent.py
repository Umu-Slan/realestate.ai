"""
Memory Agent - tracks customer memory across messages and conversations.
Loads prior profile, merges new facts from intent + qualification, persists, outputs.
Distinguishes explicit vs inferred facts; avoids overwriting strong with weak.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import MemoryAgentOutput
from orchestration.agents.memory_schema import CustomerMemoryProfile
from orchestration.agents.memory_store import load_customer_profile, save_customer_profile
from orchestration.agents.memory_merger import merge_into_profile


class MemoryAgent:
    name = "memory"

    def run(self, context: AgentContext) -> AgentResult:
        """
        Aggregate conversation context, load prior memory, merge new facts, persist, output.
        Runs after intent and lead_qualification so it can merge both.
        """
        try:
            history = context.conversation_history or []
            identity = context.identity_resolution or {}
            intent = context.intent_output or {}
            qualification = context.get_qualification()

            # Skip memory update for spam
            if intent.get("is_spam"):
                output = MemoryAgentOutput(
                    conversation_summary="spam - skipped",
                    customer_type_hint="spam",
                    message_count=len(history),
                )
                context.memory_output = output.to_dict()
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    metadata={"skipped": "spam"},
                )

            # Customer type hint
            customer_type_hint = "new_lead"
            if identity.get("matched"):
                customer_type_hint = "existing_customer"
            if context.response_mode == "support":
                customer_type_hint = "support_customer"
            if intent.get("is_broker"):
                customer_type_hint = "broker"

            # Load prior profile from DB
            customer_id = context.customer_id
            identity_id = identity.get("identity_id")
            profile = load_customer_profile(customer_id=customer_id, identity_id=identity_id)

            # Merge new facts from intent entities and qualification
            intent_entities = intent.get("entities") or {}
            intent_conf = float(intent.get("confidence", 0.5))
            qual_conf = str(qualification.get("confidence", "unknown"))
            updated = merge_into_profile(
                profile,
                intent_entities=intent_entities,
                qualification=qualification,
                message_text=context.message_text or "",
                intent_confidence=intent_conf,
                qualification_confidence=qual_conf,
            )

            # Persist if we have a customer
            persisted = False
            if customer_id or identity_id:
                persisted = save_customer_profile(
                    profile,
                    customer_id=customer_id,
                    identity_id=identity_id,
                    source="memory_agent",
                    conversation_id=context.conversation_id,
                )

            # Prior intents from history (simplified)
            prior_intents = []
            for m in history[-6:]:
                if m.get("role") == "user" and m.get("content"):
                    prior_intents.append("user_message")

            # Key facts summary from profile for backward compat
            key_facts = []
            if profile.budget:
                key_facts.append(f"budget: {profile.budget}")
            if profile.preferred_locations:
                key_facts.append(f"locations: {', '.join(profile.preferred_locations[:3])}")
            if profile.property_type:
                key_facts.append(f"property_type: {profile.property_type}")
            if profile.investment_vs_residence:
                key_facts.append(f"purpose: {profile.investment_vs_residence}")
            if profile.timeline:
                key_facts.append(f"timeline: {profile.timeline}")

            summary = f"{len(history)} messages, customer_type={customer_type_hint}, profile_updates={updated}"

            output = MemoryAgentOutput(
                conversation_summary=summary,
                customer_type_hint=customer_type_hint,
                key_facts=key_facts[:10],
                prior_intents=prior_intents[-5:],
                message_count=len(history),
                customer_profile=profile.to_dict(),
            )
            context.memory_output = output.to_dict()

            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "message_count": len(history),
                    "customer_type_hint": customer_type_hint,
                    "profile_updates": updated,
                    "persisted": persisted,
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
