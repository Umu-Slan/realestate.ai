"""
Response Composer Agent - production-grade final reply composition.
Uses all agent outputs: intent, memory, lead score, buyer stage, retrieval,
recommendations, sales strategy, objection handling, conversation plan.
Arabic-first, natural, varied, context-aware.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.schemas import ResponseComposerAgentOutput
from engines.response_composer_engine import (
    compose_sales_response,
    compose_support_response,
    compose_recommendation_response,
)


class ResponseComposerAgent:
    name = "response_composer"

    def run(self, context: AgentContext) -> AgentResult:
        """Compose natural, persuasive response from all agent outputs."""
        try:
            response_mode = context.response_mode
            intent = context.intent_output or {}
            memory = context.get_memory()
            qualification = context.get_qualification()
            retrieval = context.retrieval_output or {}
            recommendation = context.recommendation_output or {}
            strategy = context.sales_strategy_output or {}
            persuasion = context.persuasion_output or {}
            plan = context.conversation_plan_output or {}
            journey = context.journey_stage_output or {}
            routing = context.routing_output or {}
            history = context.conversation_history or []
            lang = context.lang or "ar"
            use_llm = context.use_llm

            reply_text = ""
            cta = "nurture"
            reasoning = ""
            composed_from: list[str] = []

            # Recommendation mode
            if response_mode == "recommendation":
                reply_text, cta, reasoning = compose_recommendation_response(
                    recommendation=recommendation,
                    lang=lang,
                    use_llm=use_llm,
                )
                composed_from = ["recommendation", "property_matching", "lead_qualification"]

            # Support mode
            elif response_mode == "support" or intent.get("is_support"):
                routing_ctx = dict(routing)
                routing_ctx.setdefault("queue", qualification.get("support_category", ""))
                routing_ctx.setdefault("category", strategy.get("queue", ""))
                reply_text, cta, reasoning = compose_support_response(
                    context.message_text,
                    intent=intent,
                    routing=routing_ctx,
                    conversation_history=history,
                    use_llm=use_llm,
                )
                composed_from = ["sales_strategy", "intent", "support_engine"]

            # Sales mode (includes objection handling)
            elif response_mode == "sales" or not response_mode:
                reply_text, cta, reasoning = compose_sales_response(
                    context.message_text,
                    intent=intent,
                    memory=memory,
                    qualification=qualification,
                    retrieval=retrieval,
                    recommendation=recommendation,
                    strategy=strategy,
                    persuasion=persuasion,
                    conversation_plan=plan,
                    journey_stage=journey,
                    conversation_history=history,
                    has_verified_pricing=retrieval.get("has_verified_pricing", False),
                    use_llm=use_llm,
                    lang=lang,
                )
                composed_from = [
                    "sales_strategy", "retrieval", "lead_qualification",
                    "persuasion", "conversation_plan", "journey_stage",
                    "sales_engine", "objection_library",
                ]

            # Fallback - generic LLM
            else:
                from core.adapters.llm import get_llm_client
                parts = []
                for s in retrieval.get("retrieval_sources", [])[:5]:
                    title = s.get("document_title", "") or ""
                    snip = (s.get("content_snippet") or "")[:150] if s.get("content_snippet") else ""
                    parts.append(f"[{title}]" + (f": {snip}" if snip else ""))
                retrieval_ctx = "\n\n".join(parts).strip() or retrieval.get("structured_summary", "")
                safe = ""
                if retrieval.get("retrieval_error") or not retrieval.get("has_verified_pricing"):
                    safe = " Do NOT state exact prices unless from verified data."
                messages = [
                    {"role": "system", "content": f"You are a real estate assistant. Context: {retrieval_ctx[:500]}. Be helpful.{safe}"},
                    {"role": "user", "content": context.message_text},
                ]
                reply_text = get_llm_client().chat_completion(messages)
                cta = "nurture"
                reasoning = "fallback | generic_llm"
                composed_from = ["retrieval", "generic_llm"]

            output = ResponseComposerAgentOutput(
                reply_text=reply_text or "",
                cta=cta,
                reasoning_summary_for_operator=reasoning or "",
                composed_from=composed_from,
                draft_response=reply_text or "",
            )
            context.response_composer_output = output.to_dict()
            return AgentResult(
                agent_name=self.name,
                success=True,
                metadata={
                    "composed_from": composed_from,
                    "cta": cta,
                    "reply_length": len(reply_text or ""),
                },
            )
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, error=str(e))
