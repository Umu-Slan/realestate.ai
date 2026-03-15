# Demo Readiness Checklist

Use this before internal demo or stakeholder review.

## Environment

- [ ] `.env` configured from `.env.example`
- [ ] `DATABASE_URL` points to PostgreSQL with pgvector
- [ ] `DEMO_MODE=true` if using mock LLM (no API key needed)
- [ ] `OPENAI_API_KEY` set if using live LLM

## Data

- [ ] `python manage.py migrate` — all migrations applied
- [ ] `python manage.py make_demo_ready` — projects, customers, CRM seeded
- [ ] `python manage.py load_demo_users` — admin, operator, reviewer, demo
- [ ] `python manage.py load_demo_scenarios` — evaluation scenarios loaded
- [ ] `python manage.py load_demo_data` — sample conversations with snapshots

## Health

- [ ] `GET /health/` returns 200 with at least db + model ok
- [ ] `GET /health/db/` — 200
- [ ] `GET /health/vector/` — 200 (pgvector installed)

## Acceptance Criteria

- [ ] Orchestration runs produce audit logs (`run_id` in payload)
- [ ] Scored leads include `reason_codes` in scoring
- [ ] Escalations include `handoff_summary`
- [ ] Guardrails block unverified exact prices
- [ ] CRM import always returns summary (even on malformed file)

## Smoke Tests

- [ ] `pytest demo/tests.py -v` — all pass
- [ ] `python manage.py run_demo_eval --no-llm` — completes

## UI

- [ ] `/console/` — dashboard loads
- [ ] `/console/conversations/` — list loads
- [ ] `/console/demo/eval/` — scenarios load, replay works
- [ ] `/admin/` — login with admin/demo123!

## Demo Flow

- [ ] Pick scenario in Demo Eval, run, inspect output
- [ ] Open conversation, see messages, intent, score, qualification
- [ ] Open customer profile, see timeline
- [ ] Health page shows green for db, vector, model

## Notes

- Change `demo123!` before any external access
- Redis optional for local demo; Celery may be unavailable
