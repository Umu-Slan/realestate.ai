# Controlled Orchestration Layer

## Overview

The orchestration layer is a **non-chaotic, auditable pipeline** that separates:
- Understanding
- Decision
- Response drafting
- Action execution
- Escalation

It uses a **clear orchestrator service / state machine** — no autonomous swarm.

## Pipeline Stages

| Stage | Description | Output |
|-------|-------------|--------|
| 1. Intake normalization | Validate and normalize raw message | IntakeInput |
| 2. Identity/context resolution | Resolve customer identity | identity_resolution |
| 3. Intent classification | Classify intent (multi-label) | intent_result |
| 4. Qualification extraction | Extract budget, location, etc. | qualification |
| 5. Scoring or categorization | Score lead or categorize support | scoring, routing |
| 6. Retrieval planning | Plan what to retrieve | retrieval_plan |
| 7. Response drafting | Generate draft (LLM) | draft_response |
| 8. Policy/guardrail check | Apply guardrails, rewrite if needed | policy_decision, final_response |
| 9. Action execution | Determine next best action | actions_triggered |
| 10. Audit logging | Log each stage | audit_log_ids |

## State Flow

```
INTAKE_NORMALIZATION
    → IDENTITY_CONTEXT_RESOLUTION
    → INTENT_CLASSIFICATION
    → QUALIFICATION_EXTRACTION
    → SCORING_OR_CATEGORIZATION
    → RETRIEVAL_PLANNING
    → RESPONSE_DRAFTING
    → POLICY_GUARDRAIL_CHECK
    → ACTION_EXECUTION
    → AUDIT_LOGGING
    → COMPLETED | FAILED | ESCALATED
```

## Response Policies

| Policy | Use Case |
|--------|----------|
| sales_mode | New/warm lead, normal sales tone |
| support_mode | Existing customer, support inquiry |
| clarification_mode | Low confidence, need clarification |
| escalation_mode | Angry customer, legal issue |
| safe_answer_mode | Unverified data, use safe fallback |
| unavailable_data_mode | Structured source unavailable |
| quarantine | Spam / noise |

## Guardrails

| Violation | Action |
|-----------|--------|
| Unverified exact price | Rewrite to safe form |
| Unverified exact availability | Rewrite to safe form |
| Legal advice | Block, force escalation |
| Promise of delivery | Rewrite |
| Internal company-only info | Block |
| Unsupported claims | Rewrite |

## Policy Engine

- **Block**: `allow_response=False`, provide `safe_rewrite`
- **Rewrite**: `rewrite_to_safe=True`, replace with `safe_rewrite`
- **Force escalation**: `force_escalation=True`
- **Request clarification**: `request_clarification=True`

## Next Best Action

| Action | When |
|--------|------|
| ask_budget | Budget missing, cold/warm lead |
| ask_preferred_area | Location missing |
| send_brochure | Brochure requested, warm lead |
| recommend_project | Project/price inquiry |
| request_scheduling | Visit/schedule interest, hot lead |
| create_support_case | Support inquiry |
| escalate_to_human | Escalation ready, legal, etc. |
| nurture_content | Cold/nurture lead |
| clarify_intent | Ambiguous, low confidence |

## Handoff Summary

Generated for human escalation:
- customer_type
- intent_summary
- qualification_summary
- score_and_category
- risk_notes
- recommended_next_step
- routing (route, queue, handoff_type)

## Failure Handling

| Failure | Behavior |
|---------|----------|
| Empty content | Fail at intake, `failure_reason=empty_content` |
| LLM timeout | Catch, use fallback message |
| Retrieval failure | Log, continue with empty context |
| Intelligence pipeline error | Fail run, log reason |
| Contradictory fields | Handled by intelligence layer |
| Low confidence | `requires_clarification`, next action = clarify |

## Audit Logs

Every run creates:
- `orchestration_started` – run begin
- `orchestration_stage` – per-stage (with stage name and output)
- `orchestration_completed` – success
- `orchestration_failed` – on exception

## API

### POST /api/orchestration/run/

```json
{
  "content": "What projects do you have?",
  "channel": "web",
  "external_id": "user_123",
  "phone": "",
  "email": "",
  "conversation_id": 1,
  "conversation_history": [],
  "customer_id": 1,
  "use_llm": true
}
```

Response includes: `run_id`, `status`, `intent`, `qualification`, `scoring`, `routing`, `response`, `handoff_summary`, `actions_triggered`, `escalation_flags`.

## Test Instructions

```bash
DATABASE_URL=sqlite:///test.db pytest orchestration/tests.py -v
```

Tests cover:
- Pipeline stage order
- Intake normalization
- Empty content failure
- End-to-end orchestration
- Audit log creation
- Guardrail violations (price, legal)
- Policy engine (rewrite, quarantine)
- Next best action logic
- Handoff summary
- Retrieval planning
