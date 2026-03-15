"""
Multi-agent AI sales platform - production-grade agent layer.
Each agent has a clear input/output contract and is inspectable/loggable.
"""
from orchestration.agents.base import Agent, AgentContext, AgentResult
from orchestration.agents.registry import (
    AGENT_REGISTRY,
    get_agent,
    run_agent_pipeline,
    register_agent,
)
from orchestration.agents.bootstrap import DEFAULT_AGENT_PIPELINE, SALES_AGENT_PIPELINE

# Bootstrap agents on import
from orchestration.agents import bootstrap  # noqa: F401

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "AGENT_REGISTRY",
    "get_agent",
    "run_agent_pipeline",
    "register_agent",
    "DEFAULT_AGENT_PIPELINE",
    "SALES_AGENT_PIPELINE",
]
