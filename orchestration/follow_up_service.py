"""
Follow-up Service - invokes Follow-up Agent for dormant leads.
Use from cron jobs, management commands, or async tasks.
Returns structured recommendations; caller persists. Never auto-sends.
"""
from typing import Optional

from orchestration.agents.registry import get_agent
from orchestration.agents.base import AgentContext


def run_follow_up_for_lead(
    *,
    buyer_stage: str = "",
    lead_score: int = 0,
    last_discussed_projects: list[str] | None = None,
    time_since_last_interaction_hours: float = 0.0,
    lead_ref: str = "",
    customer_id: Optional[int] = None,
    external_id: str = "",
    lang: str = "ar",
) -> dict:
    """
    Run Follow-up Agent for a single lead. Returns structured output.
    Persist recommendations via your storage layer. Does NOT send messages.

    Args:
        buyer_stage: awareness, exploration, consideration, etc.
        lead_score: 0-100
        last_discussed_projects: project names from conversation
        time_since_last_interaction_hours: hours since last message
        lead_ref: ref for storage/audit
        customer_id: optional
        external_id: optional
        lang: ar | en
    """
    agent = get_agent("follow_up")
    if not agent:
        return {"recommendations": [], "auto_send_enabled": False, "error": "follow_up agent not registered"}

    ctx = AgentContext(
        run_id="follow_up",
        follow_up_input={
            "buyer_stage": buyer_stage,
            "lead_score": lead_score,
            "last_discussed_projects": list(last_discussed_projects or []),
            "time_since_last_interaction_hours": time_since_last_interaction_hours,
            "lead_ref": lead_ref or str(customer_id or external_id or ""),
        },
        customer_id=customer_id,
        external_id=external_id,
        lang=lang,
    )
    result = agent.run(ctx)
    if not result.success:
        return {"recommendations": [], "auto_send_enabled": False, "error": result.error or "unknown"}
    return ctx.follow_up_output or {}
