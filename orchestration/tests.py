"""
Orchestration tests - pipeline, policy, guardrails, handoff.
"""
import pytest

from orchestration.states import PipelineStage, RunStatus, next_stage
from orchestration.pipeline import run_sales_pipeline
from orchestration.policy_engine import (
    check_guardrails,
    apply_policy_engine,
    ResponsePolicy,
    GuardrailViolation,
)
from orchestration.next_action import compute_next_best_action, NextBestAction
from orchestration.handoff import build_handoff_summary
from orchestration.retrieval_planner import plan_retrieval
from orchestration.orchestrator import run_orchestration, _normalize_intake


def test_sales_pipeline_runs():
    """Sales pipeline executes all 6 agents and returns reply + state."""
    result = run_sales_pipeline("I want to buy an apartment", conversation_history=[])
    assert result.reply
    assert result.agents_executed == 6
    assert "intent" in result.state
    assert result.lead_temperature in ("cold", "warm", "hot")


def test_pipeline_stage_order():
    """Stages follow deterministic order."""
    assert next_stage(PipelineStage.INTAKE_NORMALIZATION) == PipelineStage.IDENTITY_CONTEXT_RESOLUTION
    assert next_stage(PipelineStage.POLICY_GUARDRAIL_CHECK) == PipelineStage.ACTION_EXECUTION
    assert next_stage(PipelineStage.COMPLETED) is None


def test_normalize_intake():
    """Intake normalization."""
    i = _normalize_intake("  Hello  ", channel="web", external_id="u1")
    assert i.normalized_content == "Hello"
    assert i.channel == "web"
    assert i.external_id == "u1"

    i2 = _normalize_intake("")
    assert i2.validation_errors == ["empty_content"]

    # Arabic normalization: typos corrected
    i3 = _normalize_intake("عايز شقه في المعادي")
    assert "شقة" in i3.normalized_content


@pytest.mark.django_db
def test_orchestration_empty_content():
    """Empty content fails at intake."""
    run = run_orchestration("", external_id="test")
    assert run.status == RunStatus.FAILED
    assert run.failure_reason == "empty_content"


@pytest.mark.django_db
def test_orchestration_e2e_simple():
    """End-to-end orchestration runs through pipeline."""
    run = run_orchestration(
        "What projects do you have in New Cairo?",
        external_id="e2e_test",
        use_llm=False,
    )
    assert run.run_id
    assert run.intake
    assert run.intake.normalized_content
    assert run.intent_result
    assert "primary" in run.intent_result
    assert run.qualification
    assert run.scoring
    assert run.routing
    assert run.policy_decision
    assert run.final_response
    assert run.handoff_summary
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)


@pytest.mark.django_db
def test_orchestration_audit_logs():
    """Orchestration creates audit logs."""
    run = run_orchestration("Hi, I need a brochure", external_id="audit_test", use_llm=False)
    assert len(run.audit_log_ids) >= 1


def test_guardrail_unverified_price():
    """Unverified exact price triggers guardrail."""
    violations = check_guardrails(
        "The price is 2,500,000 EGP",
        has_verified_pricing=False,
    )
    assert GuardrailViolation.UNVERIFIED_EXACT_PRICE in violations


def test_guardrail_legal_advice():
    """Legal advice triggers guardrail."""
    violations = check_guardrails("Legal advice: you must sign the contract")
    assert GuardrailViolation.LEGAL_ADVICE in violations


def test_guardrail_legal_contract_validity():
    """Contract validity / legal question triggers guardrail."""
    violations = check_guardrails("Is this contract valid?")
    assert GuardrailViolation.LEGAL_ADVICE in violations or any("legal" in str(v).lower() for v in violations)
    violations2 = check_guardrails("هل هذا العقد صحيح")
    assert GuardrailViolation.LEGAL_ADVICE in violations2


def test_guardrail_internal_info():
    """Internal/restricted info triggers guardrail."""
    violations = check_guardrails("Our internal margin is 15%")
    assert GuardrailViolation.INTERNAL_ONLY_INFO in violations
    violations2 = check_guardrails("Staff only document")
    assert GuardrailViolation.INTERNAL_ONLY_INFO in violations2


def test_guardrail_unverified_availability():
    """Unverified availability triggers guardrail."""
    violations = check_guardrails("Only 5 units left available", has_verified_availability=False)
    assert GuardrailViolation.UNVERIFIED_EXACT_AVAILABILITY in violations


def test_policy_engine_rewrite():
    """Policy engine rewrites unverified price draft."""
    decision = apply_policy_engine(
        "The unit costs 3 million EGP exactly.",
        has_verified_pricing=False,
        routing={},
        intent={},
    )
    assert decision.rewrite_to_safe
    assert decision.safe_rewrite


def test_policy_engine_quarantine():
    """Quarantine routing uses quarantine policy."""
    decision = apply_policy_engine(
        "Some message",
        routing={"quarantine": True},
        intent={},
    )
    assert decision.applied_policy == ResponsePolicy.QUARANTINE


def test_policy_engine_legal_blocks_and_escalates():
    """Legal/contract question -> block, force escalation, safe handoff message."""
    decision = apply_policy_engine(
        "I need legal advice on my contract",
        has_verified_pricing=True,
        routing={"route": "legal_handoff"},
        intent={"primary": "contract_issue"},
    )
    assert decision.applied_policy == ResponsePolicy.ESCALATION_MODE
    assert decision.force_escalation
    assert "legal" in (decision.safe_rewrite or "").lower()
    assert "contract" in (decision.safe_rewrite or "").lower() or "legal" in (decision.safe_rewrite or "").lower()


def test_policy_engine_unverified_pricing_request():
    """Unverified pricing in draft -> rewrite to safe response."""
    decision = apply_policy_engine(
        "The unit costs 2.5 million EGP",
        has_verified_pricing=False,
        routing={},
        intent={"primary": "price_inquiry"},
    )
    assert decision.rewrite_to_safe
    assert decision.safe_rewrite
    assert "2.5" not in (decision.safe_rewrite or "")
    assert "Pricing" in (decision.safe_rewrite or "") or "pricing" in (decision.safe_rewrite or "").lower()


def test_policy_engine_unavailable_data_mode():
    """Unavailable project fact -> unavailable-data safe response."""
    decision = apply_policy_engine(
        "Draft that mentions some project detail",
        has_verified_pricing=False,
        routing={"unavailable_data": True},
        intent={"primary": "price_inquiry"},
    )
    assert decision.applied_policy == ResponsePolicy.UNAVAILABLE_DATA_MODE
    assert decision.rewrite_to_safe
    assert decision.safe_rewrite
    assert "verified" in (decision.safe_rewrite or "").lower() or "sales" in (decision.safe_rewrite or "").lower()


def test_policy_engine_restricted_internal_info():
    """Restricted/internal info -> block response."""
    decision = apply_policy_engine(
        "The internal margin for this project is 12%",
        has_verified_pricing=True,
        routing={},
        intent={},
    )
    assert GuardrailViolation.INTERNAL_ONLY_INFO in decision.violations
    assert decision.allow_response is False
    assert decision.safe_rewrite
    assert "specific" in (decision.safe_rewrite or "").lower() or "team" in (decision.safe_rewrite or "").lower()


def test_next_best_action_ask_budget():
    """Missing budget -> ask_budget."""
    result = compute_next_best_action(
        customer_type="new_lead",
        missing_fields=["budget", "location"],
        temperature="cold",
    )
    assert result.action == NextBestAction.ASK_BUDGET


def test_next_best_action_send_brochure():
    """Brochure intent -> send_brochure."""
    result = compute_next_best_action(
        customer_type="new_lead",
        intent_primary="brochure_request",
    )
    assert result.action == NextBestAction.SEND_BROCHURE


def test_next_best_action_escalate():
    """Escalation ready -> escalate_to_human."""
    result = compute_next_best_action(
        routing={"escalation_ready": True},
    )
    assert result.action == NextBestAction.ESCALATE_TO_HUMAN


def test_handoff_summary():
    """Handoff summary has required fields."""
    summary = build_handoff_summary(
        customer_type="new_lead",
        intent={"primary": "schedule_visit", "secondary": []},
        qualification={"budget_min": "2000000", "location_preference": "New Cairo"},
        scoring={"score": 75, "temperature": "warm"},
        routing={"route": "sales"},
        next_action={"action": "request_scheduling", "reason": "Visit interest"},
        risk_notes=[],
    )
    assert "customer_type" in summary
    assert "intent_summary" in summary
    assert "qualification_summary" in summary
    assert "score_and_category" in summary
    assert "risk_notes" in summary
    assert "recommended_next_step" in summary


def test_retrieval_plan():
    """Retrieval planner produces plan for price intent."""
    plan = plan_retrieval(
        message_text="What is the price?",
        intent_primary="price_inquiry",
    )
    assert plan.use_structured_pricing
    assert plan.query


@pytest.mark.django_db
def test_orchestration_recommendation_mode():
    """Orchestration with response_mode=recommendation uses recommend_projects."""
    run = run_orchestration(
        "Recommend: budget 1.5-3M, location New Cairo",
        external_id="rec_test",
        use_llm=False,
        response_mode="recommendation",
        qualification_override={
            "budget_min": "1500000",
            "budget_max": "3000000",
            "location_preference": "New Cairo",
        },
        lang="ar",
    )
    assert run.run_id
    assert run.status in (RunStatus.COMPLETED, RunStatus.ESCALATED)
    assert run.final_response
    assert isinstance(run.recommendation_matches, list)
    assert run.qualification.get("budget_min") == "1500000"
