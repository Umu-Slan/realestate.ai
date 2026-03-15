"""
Orchestration run schemas - inputs, stage outputs, final output.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from orchestration.states import PipelineStage, RunStatus


@dataclass
class IntakeInput:
    """Normalized intake - raw message cleaned and validated."""
    raw_content: str
    normalized_content: str
    channel: str
    external_id: str
    phone: str = ""
    email: str = ""
    name: str = ""
    conversation_id: Optional[int] = None
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class OrchestrationRun:
    """Full orchestration run - state and outputs per stage."""
    run_id: str
    status: RunStatus = RunStatus.IN_PROGRESS
    current_stage: PipelineStage = PipelineStage.INTAKE_NORMALIZATION
    intake: Optional[IntakeInput] = None
    # Stage outputs (business logic, inspectable)
    identity_resolution: dict = field(default_factory=dict)
    intent_result: dict = field(default_factory=dict)
    qualification: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)  # Customer memory profile for observability
    scoring: dict = field(default_factory=dict)
    routing: dict = field(default_factory=dict)
    journey_stage: str = ""
    retrieval_plan: dict = field(default_factory=dict)
    retrieval_sources: list = field(default_factory=list)
    draft_response: str = ""
    policy_decision: dict = field(default_factory=dict)
    final_response: str = ""
    actions_triggered: list = field(default_factory=list)
    escalation_flags: list = field(default_factory=list)
    handoff_summary: dict = field(default_factory=dict)
    has_verified_pricing: bool = True
    has_verified_availability: bool = True
    failure_reason: str = ""
    audit_log_ids: list = field(default_factory=list)
    recommendation_matches: list = field(default_factory=list)  # for response_mode=recommendation
