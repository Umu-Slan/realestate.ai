# Real Data Onboarding Design

**Date:** 2025-03-08  
**Scope:** Production-grade onboarding workflow for first real estate company.

---

## 1. Design

### 1.1 Supported Data Types

| Type | Format | Target | Notes |
|------|--------|--------|-------|
| Project documents | PDF, CSV, Excel, TXT, MD | IngestedDocument | Brochures, FAQs, SOPs, credibility |
| Project metadata | CSV | Project | name, location, price_min, price_max |
| Payment plans | CSV (same file) | ProjectPaymentPlan | installment_years, down_payment_pct |
| FAQs | PDF, TXT | IngestedDocument | document_type=faq |
| Support SOPs | PDF, TXT | IngestedDocument | document_type=support_sop |
| Company credibility | PDF, TXT | IngestedDocument | document_type=credibility |
| CRM exports | CSV, Excel | CRMRecord | Uses existing import_crm_file |

### 1.2 Models

| Model | Purpose |
|-------|---------|
| **OnboardingBatch** | Tracks a run: type, status, imported/skipped/failed/stale counts |
| **OnboardingItem** | Per-item status: source_name, status, document_id/project_id, error_message |

### 1.3 Workflow

1. **Documents**: Operator uploads files → saved to `media/onboarding/uploads/` → `ingest_file()` per file → OnboardingItem per result
2. **Structured**: Operator uploads CSV → parse rows → create/update Project + ProjectPaymentPlan
3. **CRM**: Operator uploads CSV/Excel → delegate to `import_crm_file()` → create OnboardingBatch from result
4. **Reindex**: Rebuild embeddings for documents (all or selected)

### 1.4 Verification & Source of Truth

- `IngestedDocument.source_of_truth` — set on upload form
- `IngestedDocument.verification_status` — unverified | pending | verified | stale
- `Project.pricing_source` / `availability_source` — FactSource (manual | csv_import | erp | crm)
- Onboarding batch summary: imported, skipped, failed, stale

### 1.5 Column Mapping (Structured CSV)

Flexible mapping similar to CRM:

- `name` — name, project_name, project, title
- `location` — location, area, district, region
- `price_min` / `price_max` — min_price, price_from, etc.
- `installment_years_min` — years_min, installment_years, years
- `down_payment_pct_min` — down_payment, down_payment_pct

---

## 2. Files Changed

| File | Changes |
|------|---------|
| `onboarding/` (new app) | models, views, urls, services, admin, templates |
| `knowledge/models.py` | Add `company` FK to IngestedDocument |
| `knowledge/ingestion.py` | Add `company_id` param to `ingest_file`, `ingest_from_content` |
| `knowledge/views.py` | Pass `company_id` in API ingest |
| `config/settings.py` | MEDIA_ROOT, MEDIA_URL; add onboarding app |
| `config/urls.py` | Serve media in DEBUG |
| `console/urls.py` | Include onboarding urls |
| `console/base.html` | Nav link to Onboarding |

---

## 3. Migrations

| Migration | Purpose |
|-----------|---------|
| `knowledge.0006_ingesteddocument_company` | Add company FK to IngestedDocument |
| `onboarding.0001_initial` | OnboardingBatch, OnboardingItem |

---

## 4. Tests

| Test | Coverage |
|------|----------|
| `OnboardingBatchTest.test_batch_creation` | Batch model, summary property |
| `StructuredImportTest.test_import_project_csv` | CSV import creates Project + ProjectPaymentPlan |

---

## 5. Verification Steps

1. **Run migrations**: `python manage.py migrate`
2. **Onboarding dashboard**: Visit `/console/onboarding/`
3. **Upload documents**: Select PDF, choose type (e.g. project_brochure), upload → batch created
4. **Upload structured CSV**: Create CSV with name, location, price_min → projects created
5. **Upload CRM**: Use existing CRM CSV → CRMImportBatch + OnboardingBatch
6. **Batch detail**: Click batch → see items, links to documents/projects
7. **Reindex**: Click Reindex All → embeddings rebuilt
8. **Knowledge**: Visit Knowledge → verify documents appear with verification fields

---

## 6. Remaining Risks

| Risk | Mitigation |
|------|------------|
| Large file uploads | Consider size limits; async ingestion for 100+ docs |
| Excel for structured | Not implemented; use CSV |
| Duplicate detection | Document: by file_hash (RawDocument); structured: by name+company |
| Company required | Single-company: _default_company(); multi-tenant: explicit in form |
