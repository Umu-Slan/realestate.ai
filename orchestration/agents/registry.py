"""
Agent registry - lookup and deterministic pipeline execution.
"""
import logging
from typing import Optional

from orchestration.agents.base import Agent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

AGENT_REGISTRY: dict[str, Agent] = {}


def register_agent(agent: Agent) -> None:
    """Register an agent by name."""
    AGENT_REGISTRY[agent.name] = agent


def get_agent(name: str) -> Optional[Agent]:
    """Get agent by name."""
    return AGENT_REGISTRY.get(name)


def run_agent_pipeline(
    agents: list[str],
    context: AgentContext,
    *,
    stop_on_failure: bool = False,
) -> tuple[AgentContext, list[tuple[str, AgentResult]]]:
    """
    Run agents in deterministic order. Each agent receives updated context.
    Returns (updated context, list of (agent_name, result)).
    """
    results: list[tuple[str, AgentResult]] = []
    ctx = context

    for name in agents:
        agent = get_agent(name)
        if not agent:
            logger.warning("Agent %s not found in registry, skipping", name)
            continue
        try:
            result = agent.run(ctx)
            results.append((name, result))
            if not result.success and stop_on_failure:
                logger.warning("Agent %s failed, stopping pipeline: %s", name, result.error)
                break
            # Update context with agent output (agents do this themselves via ctx)
            # Context is mutable; agents update ctx.intent_output, etc.
        except Exception as e:
            logger.exception("Agent %s raised: %s", name, e)
            from orchestration.agents.base import AgentResult
            results.append((name, AgentResult(agent_name=name, success=False, error=str(e))))
            if stop_on_failure:
                break

    return ctx, results
