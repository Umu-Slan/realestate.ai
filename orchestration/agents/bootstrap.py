"""
Bootstrap - register all agents in the registry.
Called on module import.
"""
from orchestration.agents.registry import register_agent
from orchestration.agents.intent_agent import IntentAgent
from orchestration.agents.memory_agent import MemoryAgent
from orchestration.agents.lead_qualification_agent import LeadQualificationAgent
from orchestration.agents.retrieval_agent import RetrievalAgent
from orchestration.agents.property_matching_agent import PropertyMatchingAgent
from orchestration.agents.recommendation_agent import RecommendationAgent
from orchestration.agents.sales_strategy_agent import SalesStrategyAgent
from orchestration.agents.persuasion_agent import PersuasionAgent
from orchestration.agents.journey_stage_agent import JourneyStageAgent
from orchestration.agents.conversation_plan_agent import ConversationPlanAgent
from orchestration.agents.response_composer_agent import ResponseComposerAgent
from orchestration.agents.follow_up_agent import FollowUpAgent

# Default pipeline order - deterministic
# Memory runs after lead_qualification so it can merge intent + qualification
# Journey stage runs after sales_strategy (needs routing for support path)
DEFAULT_AGENT_PIPELINE = [
    "intent",
    "lead_qualification",
    "memory",
    "retrieval",
    "property_matching",
    "recommendation",
    "sales_strategy",
    "persuasion",
    "journey_stage",
    "conversation_plan",
    "response_composer",
]

# Sales-only pipeline (no property matching/recommendation)
SALES_AGENT_PIPELINE = [
    "intent",
    "lead_qualification",
    "memory",
    "retrieval",
    "sales_strategy",
    "persuasion",
    "journey_stage",
    "conversation_plan",
    "response_composer",
]


def _register_all() -> None:
    register_agent(IntentAgent())
    register_agent(MemoryAgent())
    register_agent(LeadQualificationAgent())
    register_agent(RetrievalAgent())
    register_agent(PropertyMatchingAgent())
    register_agent(RecommendationAgent())
    register_agent(SalesStrategyAgent())
    register_agent(PersuasionAgent())
    register_agent(JourneyStageAgent())
    register_agent(ConversationPlanAgent())
    register_agent(ResponseComposerAgent())
    register_agent(FollowUpAgent())


_register_all()
