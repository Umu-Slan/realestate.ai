"""
Orchestration pipeline stages - clear state machine.
No swarm, single linear flow with deterministic transitions.
"""
from enum import Enum, auto


class PipelineStage(str, Enum):
    """Pipeline stages in order."""
    INTAKE_NORMALIZATION = "intake_normalization"
    IDENTITY_CONTEXT_RESOLUTION = "identity_context_resolution"
    INTENT_CLASSIFICATION = "intent_classification"
    QUALIFICATION_EXTRACTION = "qualification_extraction"
    SCORING_OR_CATEGORIZATION = "scoring_or_categorization"
    RETRIEVAL_PLANNING = "retrieval_planning"
    RESPONSE_DRAFTING = "response_drafting"
    POLICY_GUARDRAIL_CHECK = "policy_guardrail_check"
    ACTION_EXECUTION = "action_execution"
    AUDIT_LOGGING = "audit_logging"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class RunStatus(str, Enum):
    """Orchestration run status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


def next_stage(current: PipelineStage) -> PipelineStage | None:
    """Deterministic next stage. Returns None if terminal."""
    order = [
        PipelineStage.INTAKE_NORMALIZATION,
        PipelineStage.IDENTITY_CONTEXT_RESOLUTION,
        PipelineStage.INTENT_CLASSIFICATION,
        PipelineStage.QUALIFICATION_EXTRACTION,
        PipelineStage.SCORING_OR_CATEGORIZATION,
        PipelineStage.RETRIEVAL_PLANNING,
        PipelineStage.RESPONSE_DRAFTING,
        PipelineStage.POLICY_GUARDRAIL_CHECK,
        PipelineStage.ACTION_EXECUTION,
        PipelineStage.AUDIT_LOGGING,
        PipelineStage.COMPLETED,
    ]
    idx = order.index(current) if current in order else -1
    if idx >= 0 and idx < len(order) - 1:
        return order[idx + 1]
    return None
