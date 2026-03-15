"""
Acceptance criteria checks for v0 pilot.
Ensures every critical path meets operational standards.
"""
from typing import Any


def check_orchestration_auditable(run: Any) -> tuple[bool, str]:
    """Every orchestration run must be auditable (have run_id, audit trail)."""
    run_id = getattr(run, "run_id", "") or ""
    audit_ids = getattr(run, "audit_log_ids", [])
    if not run_id:
        return False, "run_id missing"
    if not audit_ids and getattr(run, "status", "").value != "failed":
        return False, "no audit log entries"
    return True, "ok"


def check_scored_lead_has_reason_codes(scoring: dict) -> tuple[bool, str]:
    """Every scored lead must include reason codes (can be empty for nurture)."""
    if not isinstance(scoring, dict):
        return True, "ok"
    temp = scoring.get("temperature", "")
    if not temp:
        return True, "ok"
    reason_codes = scoring.get("reason_codes", [])
    if not reason_codes and temp not in ("nurture", ""):
        return False, "reason_codes missing for scored lead"
    return True, "ok"


def check_escalation_has_handoff(run: Any) -> tuple[bool, str]:
    """Every escalation must include a handoff summary."""
    if not getattr(run, "escalation_flags", []) and not getattr(run, "routing", {}).get("escalation_ready"):
        return True, "ok"  # Not an escalation
    handoff = getattr(run, "handoff_summary", {}) or {}
    if not handoff:
        return False, "handoff_summary missing for escalation"
    return True, "ok"


def check_response_passed_guardrails(policy_decision: dict) -> tuple[bool, str]:
    """Every sensitive answer must pass guardrails (or be rewritten)."""
    violations = policy_decision.get("violations", []) if isinstance(policy_decision, dict) else []
    allow = policy_decision.get("allow_response", True)
    rewrite = policy_decision.get("rewrite_to_safe", False)
    if violations and not rewrite and allow:
        return False, f"violations {violations} not handled"
    return True, "ok"


def check_crm_batch_has_summary(result: dict) -> tuple[bool, str]:
    """Every imported CRM batch must produce a summary report."""
    required = ["total_rows", "imported", "batch_id"]
    for k in required:
        if k not in result:
            return False, f"summary missing field: {k}"
    return True, "ok"
