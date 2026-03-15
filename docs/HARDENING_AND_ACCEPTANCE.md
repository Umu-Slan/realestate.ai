# Hardening and Acceptance Criteria

## Graceful Failure Handling

| Failure Mode | Location | Behavior |
|--------------|----------|----------|
| Missing knowledge | orchestration, retrieval | Fallback: FALLBACK_MISSING_KNOWLEDGE (ar) |
| Stale knowledge | RetrievalPolicy.is_fresh | Downrank stale; fallback available |
| Structured source unavailable | get_structured_pricing | Returns None; safe response policy |
| LLM timeout | llm_openai.chat_completion | timeout param; catch → FALLBACK_LLM_TIMEOUT |
| Malformed CRM import | crm import_service | try/except; return _default_summary |
| Ambiguous identity | identity_resolution | manual_review_required; FALLBACK_AMBIGUOUS_IDENTITY |
| Low-confidence intent | pipeline, routing | requires_clarification; clarification mode |
| Low-confidence scoring | pipeline | confidence=low; nurture route |
| Contradictory qualification | pipeline | detect_contradictory_qualification; confidence=low |

## Acceptance Criteria Mapping

| Criterion | Check | Location |
|-----------|-------|----------|
| Every orchestration run auditable | run_id in audit payload; orchestration_started/completed | audit.service, orchestrator |
| Every scored lead has reason codes | run.scoring.reason_codes | orchestrator (serialize from ScoringResult) |
| Every escalation has handoff summary | handoff_summary built before completion | orchestrator |
| Every sensitive answer passes guardrails | policy_decision.violations handled | policy_engine, orchestrator |
| Every CRM batch produces summary | _default_summary on error; stats always returned | crm import_service |

## Health Endpoints

| Path | Purpose |
|------|---------|
| /health/ | Aggregated (db, redis, vector, model) |
| /health/db/ | PostgreSQL connectivity |
| /health/redis/ | Redis (Celery broker) |
| /health/celery/ | Celery workers (optional) |
| /health/vector/ | pgvector extension |
| /health/model/ | OPENAI_API_KEY or DEMO_MODE |

## Logging / Tracing

| ID | In |
|----|-----|
| correlation_id | Request header X-Correlation-Id; middleware |
| conversation_id | Audit payload when conversation_id provided |
| run_id | Audit payload for orchestration runs |
