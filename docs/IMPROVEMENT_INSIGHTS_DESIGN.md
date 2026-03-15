# Improvement Insights – Design & Implementation

**Date:** 2025-03-09  
**Goal:** Safe AI self-improvement foundation on top of existing real estate AI system.

---

## 1. Design Choices

### 1.1 Principles

- **No autonomous self-modifying AI** – Suggestions are reviewable only; no automatic prompt/model changes
- **Controlled improvement** – Aggregation runs on demand (console “Refresh”)
- **Based on logged outcomes** – Signals from HumanCorrection, Escalation, SupportCase, OrchestrationSnapshot, etc.
- **Architecture preserved** – New `improvement` app; no redesign of orchestration, scoring, support, etc.

### 1.2 Data Model

**ImprovementSignal** – One row per observed pattern:
- `issue_type`: corrected_response | escalation_reason | support_category | objection_type | low_confidence | failed_recommendation | missing_qualification | score_routing_disagreement
- `source_feature`: sales | support | orchestration | qualification | scoring | recommendation | knowledge | guardrails
- `pattern_key`: identifier (e.g. objection key, category, field name)
- `frequency`, `affected_mode`, `affected_intent`
- `example_refs`: JSON list of `{type, id}` for conversation, message, correction, escalation, support_case, recommendation
- `recommended_action`: operator-facing text (e.g. “Add FAQ knowledge about X”)
- `review_status`: pending | reviewed | accepted | dismissed

### 1.3 Aggregation Sources

| Signal type | Source | Logic |
|-------------|--------|-------|
| corrected_response | HumanCorrection, ResponseFeedback (is_good=False) | By issue_type/field_name, mode |
| escalation_reason | Escalation.reason | Count by reason |
| support_category | SupportCase.category | Count by category |
| objection_type | Message (user) + detect_objection | Sample messages, infer objection |
| low_confidence | OrchestrationSnapshot | intent.confidence or scoring.confidence < 0.6 |
| missing_qualification | LeadQualification | Budget, property_type, location, timeline null/blank |
| score_routing_disagreement | OrchestrationSnapshot | route=sales + temp=cold, or route=support + purchase intent |
| failed_recommendation | Recommendation + Escalation | Conversations with both; by project_id |

---

## 2. Files Changed

| File | Change |
|------|--------|
| `config/settings.py` | Added `improvement` to INSTALLED_APPS |
| `console/views.py` | Added `improvement_insights` view |
| `console/urls.py` | Added path `improvement/` |
| `console/templates/console/base.html` | Added nav link “Improvement” |
| `console/templates/console/improvement_insights.html` | **New** – Improvement Insights page |

## 3. Files Created

| File | Purpose |
|------|---------|
| `improvement/__init__.py` | Package init |
| `improvement/apps.py` | App config |
| `improvement/models.py` | ImprovementSignal model |
| `improvement/admin.py` | Admin for ImprovementSignal |
| `improvement/services/__init__.py` | Services package |
| `improvement/services/aggregation.py` | `aggregate_improvement_signals()` |
| `improvement/services/recommendations.py` | `generate_operator_recommendations()` |
| `improvement/migrations/__init__.py` | Migrations package |
| `improvement/migrations/0001_initial.py` | Initial migration |
| `improvement/tests.py` | Tests for aggregation logic |
| `docs/IMPROVEMENT_INSIGHTS_DESIGN.md` | This document |

---

## 4. Migrations Created

- `improvement/migrations/0001_initial.py` – Creates `improvement_improvementsignal` table  
- Depends on `companies.0001_initial`  
- Run: `manage.py migrate improvement`

---

## 5. Tests Added/Updated

| Test | Purpose |
|------|---------|
| `test_upsert_signal_creates_new` | Create new signal |
| `test_upsert_signal_updates_existing` | Update frequency when pattern exists |
| `test_aggregate_escalation_reasons` | Escalation aggregation |
| `test_aggregate_support_categories` | SupportCase aggregation |
| `test_aggregate_improvement_signals_returns_counts` | Full aggregation returns dict |
| `test_generate_operator_recommendations` | Recommendations from signals |

Run: `pytest improvement/tests.py -v`

---

## 6. New Console Pages

**Improvement Insights** (`/console/improvement/`)

- Period selector (7/30/90 days)
- “Refresh Insights” – triggers aggregation
- Top recurring failure patterns
- Operator recommendations
- By issue type groups
- Example recommendations (add FAQ, tighten guardrail, etc.)

---

## 7. Verification Steps

1. **Migrate**
   ```bash
   .venv\Scripts\python.exe manage.py migrate improvement
   ```

2. **Run tests**
   ```bash
   .venv\Scripts\python.exe -m pytest improvement/tests.py -v
   ```

3. **Console page**
   - Start server: `manage.py runserver`
   - Go to http://localhost:8000/console/improvement/
   - Click “Refresh Insights”
   - Verify signals and recommendations appear (may be empty if no data in period)

4. **Admin**
   - http://localhost:8000/admin/improvement/improvementsignal/

---

## 8. Risks & Follow-up

| Risk | Mitigation |
|------|------------|
| Heavy aggregation on large datasets | Sample limits (e.g. 2000 messages for objections); add `celery` task for async refresh later |
| Duplicate signals across runs | `_upsert_signal` merges by (issue_type, pattern_key, mode, intent, company) |
| Company-scoping for multi-tenant | `company_id` on model; aggregation uses `get_default_company()` for first company |

**Future work**
- Management command `aggregate_improvement_signals` for cron/scheduled refresh
- API endpoint for improvement insights (e.g. for external dashboards)
- Review workflow: mark as accepted/dismissed with audit trail
- Link example_refs to conversation/message detail pages in console
