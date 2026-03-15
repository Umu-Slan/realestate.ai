"""
Agent base interface and context - clear contracts for all agents.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class Agent(Protocol):
    """Protocol for all agents. Clear input via context, structured output."""

    name: str

    def run(self, context: "AgentContext") -> "AgentResult":
        """Execute agent logic. Returns structured, inspectable result."""
        ...


@dataclass
class AgentResult:
    """
    Base result for all agents. Inspectable and loggable.
    Subclasses add agent-specific output fields.
    """
    agent_name: str
    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_loggable(self) -> dict:
        """Serialize for audit/logging. Exclude large payloads if needed."""
        out = {
            "agent": self.agent_name,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }
        return out


@dataclass
class AgentContext:
    """
    Shared context passed through the agent pipeline.
    Populated incrementally by each agent. All fields optional for flexibility.
    """
    # Intake
    run_id: str = ""
    message_text: str = ""
    conversation_history: list = field(default_factory=list)
    channel: str = "web"
    external_id: str = ""
    customer_id: Optional[int] = None
    conversation_id: Optional[int] = None
    response_mode: Optional[str] = None  # sales | support | recommendation | None
    qualification_override: Optional[dict] = None
    use_llm: bool = True
    lang: str = "ar"
    is_angry: bool = False

    # Identity (from orchestration stage 2)
    identity_resolution: dict = field(default_factory=dict)

    # Agent outputs (populated as pipeline runs)
    intent_output: Optional[dict] = None
    memory_output: Optional[dict] = None
    qualification_output: Optional[dict] = None
    retrieval_output: Optional[dict] = None
    property_matching_output: Optional[dict] = None
    recommendation_output: Optional[dict] = None
    market_context_output: Optional[dict] = None  # Aggregated market context for sales strategy
    sales_strategy_output: Optional[dict] = None
    persuasion_output: Optional[dict] = None
    journey_stage_output: Optional[dict] = None
    conversation_plan_output: Optional[dict] = None
    response_composer_output: Optional[dict] = None
    routing_output: Optional[dict] = None  # from sales_strategy (apply_routing_rules)
    follow_up_output: Optional[dict] = None  # from follow_up agent (standalone invocation)
    # For follow-up agent: pass lead context via follow_up_input
    follow_up_input: Optional[dict] = None  # buyer_stage, lead_score, last_discussed_projects, time_since_last_hours, lead_ref

    def get_intent(self) -> Optional[dict]:
        return self.intent_output

    def get_qualification(self) -> dict:
        """Merged qualification: agent output + override."""
        q = dict(self.qualification_output or {})
        if self.qualification_override:
            for k, v in self.qualification_override.items():
                if v is not None and v != "":
                    q[k] = str(v) if not isinstance(v, str) else v
        return q

    def get_memory(self) -> dict:
        """Structured customer memory for downstream agents. Includes customer_profile."""
        mem = dict(self.memory_output or {})
        return mem
