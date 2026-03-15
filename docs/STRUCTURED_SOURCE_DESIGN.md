# Structured Source Layer – Design

Structured source of truth for inventory, pricing, payment plans, and delivery. Prepared for real company onboarding and future ERP/CRM integration.

---

## 1. Structured Source Design

### Models

| Model | Purpose |
|-------|---------|
| **Project** (extended) | `pricing_source`, `availability_source` – origin tracking for future sync |
| **ProjectPaymentPlan** | Down payment %, installment years; one per project (or per phase) |
| **ProjectDeliveryTimeline** | Phase name, expected start/end dates; multiple per project |
| **ProjectUnitCategory** | Category name, price range, optional `quantity_available` for inventory |

### Verification

- Each fact has `last_verified_at`. If within 90 days → **verified**.
- Verified facts can be stated as authoritative; unverified trigger safe fallback language.
- `FactSource` enum: `manual`, `csv_import`, `erp`, `crm` – for future integration.

### Service API

- `get_project_structured_facts(project_id)` → `ProjectStructuredFacts` with:
  - `pricing`, `payment_plan`, `availability`, `delivery`, `unit_categories`
  - Each has `value`, `is_verified`, `last_verified_at`, `source`
- `get_safe_language_for_fact(fact_type, has_value, is_verified, lang)` → disclaimer text
- `format_pricing_for_response(facts, lang, include_disclaimer)` → formatted string

---

## 2. Design Choices

1. **Per-fact verification** – Pricing, payment plan, delivery, availability can be verified independently.
2. **90-day staleness** – Facts are considered verified only if `last_verified_at` is within 90 days.
3. **ERP-ready fields** – `source`, `quantity_available` (unit category), structured relations for sync.
4. **Backward compatible** – Project keeps `price_min`, `price_max`, `availability_status`; retrieval/policy unchanged.
5. **Single source for response layer** – `get_structured_pricing` / `get_structured_availability` delegate to `get_project_structured_facts`.

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `core/enums.py` | Added `FactSource` (manual, csv_import, erp, crm) |
| `knowledge/models.py` | Added `pricing_source`, `availability_source` on Project; `ProjectPaymentPlan`, `ProjectDeliveryTimeline`, `ProjectUnitCategory` |
| `knowledge/services/structured_facts.py` | New: `get_project_structured_facts`, `get_safe_language_for_fact`, `format_pricing_for_response` |
| `knowledge/retrieval.py` | `get_structured_pricing`, `get_structured_availability` use structured facts service; return `is_verified` |
| `knowledge/admin.py` | Inlines for payment plan, delivery, unit category; registered new models |
| `engines/recommendation_engine.py` | `has_verified_pricing` from `get_project_structured_facts` |
| `console/views.py` | `structured_facts`, `structured_facts_project` |
| `console/urls.py` | Routes for structured facts |
| `console/templates/console/base.html` | Nav link for Structured Facts |
| `console/templates/console/structured_facts.html` | List projects with verification summary |
| `console/templates/console/structured_facts_project.html` | Project detail with all facts |
| `knowledge/tests.py` | Tests for verified vs unverified, payment plan, delivery, safe language |

---

## 4. Migrations Created

- **knowledge/migrations/0004_structured_facts.py**
  - `Project`: `pricing_source`, `availability_source`
  - `ProjectPaymentPlan`, `ProjectDeliveryTimeline`, `ProjectUnitCategory`

---

## 5. Tests Added/Updated

| Test | Purpose |
|------|---------|
| `test_structured_facts_verified_vs_unverified` | Verified project has `is_verified=True`; unverified has `False` |
| `test_structured_facts_payment_plan_and_delivery` | Payment plan, delivery, unit categories loaded from models |
| `test_safe_language_for_unverified_fact` | `get_safe_language_for_fact` returns disclaimer when unverified |

---

## 6. Safety Logic

- **Policy engine** – Still uses `has_verified_pricing`, `has_verified_availability`; now backed by structured facts verification.
- **Recommendation engine** – `has_verified_pricing` from `get_project_structured_facts().has_verified_pricing`.
- **Response builder** – Keeps existing "(confirm with sales)" when `not has_verified_pricing`.
- **Retrieval** – Document chunks never used for exact pricing/availability; `get_structured_pricing` returns `is_verified`.

---

## 7. Verification Steps

1. `python manage.py migrate knowledge`
2. `pytest knowledge/tests.py -v`
3. Open `/console/structured-facts/` – list projects and verification status
4. Open `/console/structured-facts/<project_id>/` – inspect facts
5. Add payment plan / delivery / unit category via Django Admin
6. Re-run structured facts page – confirm new data appears

---

## 8. Risks & Follow-up

| Risk | Mitigation / Follow-up |
|------|-------------------------|
| N+1 in recommendation engine | `get_project_structured_facts` called per project; acceptable for ~20 projects; consider batch loader later |
| Manual onboarding only today | Admin inlines; CSV import command can be added to populate from spreadsheet |
| ERP/CRM integration not implemented | `source` and structure support future sync; add sync job when systems are ready |
| Unit inventory vs project availability | `quantity_available` on unit category; project-level `availability_status` for overall |
