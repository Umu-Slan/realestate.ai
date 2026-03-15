"""
Central orchestration layer - structured agent pipeline for sales.
Flow: Intent → Entity → Memory → LeadScore → Recommendation → ResponseComposer.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from orchestration.pipeline_agents import (
    IntentAgent,
    EntityExtractionAgent,
    ConversationMemoryAgent,
    LeadScoringAgent,
    RecommendationAgent,
    ResponseComposerAgent,
    IntentAgentOutput,
    EntityExtractionOutput,
    ConversationState,
    RecommendationOutput,
)

# Pipeline logger - writes to logs/pipeline.log
PIPELINE_LOG_DIR = "logs"
PIPELINE_LOG_FILE = "pipeline.log"


def _get_pipeline_logger() -> logging.Logger:
    """Logger that writes to logs/pipeline.log."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), PIPELINE_LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, PIPELINE_LOG_FILE)
    logger = logging.getLogger("orchestration.pipeline")
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@dataclass
class PipelineResult:
    """Output of run_sales_pipeline."""
    reply: str
    state: dict
    lead_temperature: str
    recommendations: list
    intent: str = ""
    confidence: float = 0.0
    agents_executed: int = 0
    agent_logs: list[str] = field(default_factory=list)


def run_sales_pipeline(
    user_message: str,
    *,
    conversation_history: Optional[list] = None,
    prior_state: Optional[dict] = None,
) -> PipelineResult:
    """
    Run full agent pipeline on user message.
    Returns { reply, state, lead_temperature, recommendations }.
    """
    history = conversation_history or []
    agent_logs: list[str] = []

    # Restore prior state
    prev_state: Optional[ConversationState] = None
    if prior_state:
        prev_state = ConversationState(
            intent=prior_state.get("intent", ""),
            budget=prior_state.get("budget"),
            location=prior_state.get("location"),
            property_type=prior_state.get("property_type"),
            stage=prior_state.get("stage", "qualification"),
            lead_score=prior_state.get("lead_score", 0),
            lead_temperature=prior_state.get("lead_temperature", "cold"),
        )

    # 1. IntentAgent
    intent_agent = IntentAgent()
    intent_out = intent_agent.run(user_message, history)
    agent_logs.append(f"IntentAgent -> {intent_out.intent}")
    _get_pipeline_logger().info("IntentAgent -> %s", intent_out.intent)

    # 2. EntityExtractionAgent
    entity_agent = EntityExtractionAgent()
    entity_out = entity_agent.run(user_message)
    agent_logs.append(f"EntityAgent -> budget={entity_out.budget} location={entity_out.location}")
    _get_pipeline_logger().info("EntityAgent -> budget=%s location=%s", entity_out.budget, entity_out.location)

    # 3. ConversationMemoryAgent (merge prior + new, no lead yet)
    memory_agent = ConversationMemoryAgent()
    state = memory_agent.run(prev_state, intent_out.intent, entity_out, lead_output=None)

    # 4. LeadScoringAgent (score merged state)
    lead_agent = LeadScoringAgent()
    lead_out = lead_agent.run(state)
    state.lead_score = lead_out["lead_score"]
    state.lead_temperature = lead_out["lead_temperature"]
    agent_logs.append("MemoryAgent -> state updated")
    _get_pipeline_logger().info("MemoryAgent -> state updated: %s", state.to_dict())

    # 5. RecommendationAgent (only when buy_property + location + budget)
    rec_agent = RecommendationAgent()
    rec_out = rec_agent.run(intent_out.intent, state)
    agent_logs.append(f"RecommendationAgent -> {len(rec_out.recommended_projects)} projects")
    _get_pipeline_logger().info("RecommendationAgent -> %s projects", len(rec_out.recommended_projects))

    # 6. ResponseComposerAgent
    composer_agent = ResponseComposerAgent()
    reply = composer_agent.run(
        user_message,
        intent_out.intent,
        state,
        rec_out,
        lead_out["lead_temperature"],
    )
    agent_logs.append(f"ResponseComposer -> reply generated")
    _get_pipeline_logger().info("ResponseComposer -> reply generated")

    _get_pipeline_logger().info("--- Pipeline complete ---")

    return PipelineResult(
        reply=reply,
        state=state.to_dict(),
        lead_temperature=lead_out["lead_temperature"],
        recommendations=[
            {**p, "match_score": rec_out.match_scores[i] if i < len(rec_out.match_scores) else None}
            for i, p in enumerate(rec_out.recommended_projects)
        ],
        intent=intent_out.intent,
        confidence=intent_out.confidence,
        agents_executed=6,
        agent_logs=agent_logs,
    )
