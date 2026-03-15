# Observability Implementation

**Date:** 2025-03-08  
**Scope:** Production-grade structured logging, correlation IDs, health endpoints, operator visibility.

---

## 1. Design

### 1.1 Structured Logging

- **Logger:** `realestate.observability` — dedicated logger for pipeline events
- **Format:** Standard log message + `| obs={...}` JSON payload for log aggregation (correlation_id, run_id, event, etc.)
- **Context vars:** `correlation_id`, `conversation_id`, `run_id` — request-scoped, set by middleware/orchestration, attached to all events
- **Content truncation:** Strings in `content`, `message`, `raw_content`, `error` truncated to 500 chars for safety

### 1.2 Event Types Logged

| Event | Level | When |
|-------|-------|------|
| `inbound_message` | INFO | Web/WhatsApp message received |
| `orchestration_start` | INFO | Pipeline run started |
| `orchestration_complete` | INFO | Pipeline run finished (status, route, temperature) |
| `orchestration_failed` | ERROR | Pipeline failed (reason, stage) |
| `scoring` | INFO | LeadScore persisted |
| `recommendation` | INFO | Recommendation matches persisted |
| `support_case_created` | INFO | SupportCase created |
| `escalation_created` | INFO | Escalation created |
| `crm_sync` | INFO | CRM record updated |
| `pipeline_failure` | ERROR | Component failure (persistence, WhatsApp pipeline) |

### 1.3 Correlation / IDs

- **X-Correlation-Id:** Set per HTTP request (header or generated). Echoed in response. Bound to context via middleware.
- **conversation_id:** Set when conversation is known (orchestration entry).
- **run_id:** Set at orchestration start; propagates through pipeline.

### 1.4 Health Endpoints

- `/health/` — Aggregated (db, redis, vector, model). Returns 503 if < 2 ok.
- `/health/ready/` — Readiness probe: DB only. Use for load balancers / k8s.
- `/health/db/`, `/health/redis/`, `/health/vector/`, `/health/model/` — Individual checks.

---

## 2. Files Changed

| File | Changes |
|------|---------|
| `core/observability.py` | Already present: context vars, event helpers, ObservabilityFormatter |
| `core/middleware.py` | Bind correlation_id to context on request; clear on response |
| `core/health_views.py` | Extract `run_health_checks()`; add `health_ready` |
| `core/health_urls.py` | Add `/health/ready/` route |
| `config/settings.py` | Add LOGGING config for `realestate.observability` |
| `orchestration/service.py` | log_inbound, bind_context (conversation_id); log_pipeline_failure on persistence error |
| `orchestration/orchestrator.py` | log_orchestration_start, log_orchestration_complete, log_orchestration_failed |
| `orchestration/persistence.py` | log_scoring, log_recommendation, log_support_case_created, log_escalation_created |
| `channels/service.py` | log_inbound; log_pipeline_failure on WhatsApp pipeline failure |
| `crm/services/sync_service.py` | log_crm_sync in sync_conversation_outcome |
| `console/views.py` | Add `operations` view |
| `console/urls.py` | Add `/console/operations/` |
| `console/templates/console/base.html` | Add Operations nav link |
| `console/templates/console/operations.html` | New: health checks, operational state, recent pipeline runs |

---

## 3. Migrations

None. No model changes.

---

## 4. Tests

| File | Tests |
|------|-------|
| `core/tests_observability.py` | 13 tests: context bind/clear, log helpers, ObservabilityFormatter |

```
core/tests_observability.py::TestObservabilityContext::test_get_context_empty
core/tests_observability.py::TestObservabilityContext::test_bind_and_get_context
core/tests_observability.py::TestObservabilityContext::test_bind_partial
core/tests_observability.py::TestObservabilityContext::test_clear_context
core/tests_observability.py::TestObservabilityLogging::test_log_inbound
core/tests_observability.py::TestObservabilityLogging::test_log_orchestration_start
core/tests_observability.py::TestObservabilityLogging::test_log_orchestration_complete
core/tests_observability.py::TestObservabilityLogging::test_log_orchestration_failed
core/tests_observability.py::TestObservabilityLogging::test_log_scoring
core/tests_observability.py::TestObservabilityLogging::test_log_crm_sync
core/tests_observability.py::TestObservabilityLogging::test_log_pipeline_failure
core/tests_observability.py::TestObservabilityFormatter::test_formatter_with_obs
core/tests_observability.py::TestObservabilityFormatter::test_formatter_without_obs
```

---

## 5. Verification Steps

1. **Start app** and send a web chat message:
   ```bash
   python manage.py runserver
   # POST to /api/engines/sales/ with {"message": "شقة في الشيخ زايد"}
   ```

2. **Check logs** for structured events:
   - `inbound_message` with channel=web
   - `orchestration_start` with run_id
   - `orchestration_complete` with status, route, temperature
   - `scoring` if lead-type

3. **Health endpoints:**
   ```bash
   curl http://localhost:8000/health/
   curl http://localhost:8000/health/ready/
   ```

4. **Operations page:** Login to console, go to **Operations** — health checks, operational state, recent runs.

5. **Correlation ID:** Inspect response header `X-Correlation-Id` for any API request.

---

## 6. Remaining Risks

| Risk | Mitigation |
|------|------------|
| Log volume | Events are INFO/ERROR only; no per-token logging. Content truncated. |
| Context in async/Celery | Context vars are request-scoped. Celery tasks would need manual bind of correlation_id/run_id if added later. |
| JSON formatter in prod | Current formatter appends `obs=` to message. For pure JSON lines, consider python-json-logger or structlog. |
| Operations page load | run_health_checks() hits DB/Redis; page requires auth. Acceptable for admin use. |
