# Knowledge Management Architecture

Production-leaning knowledge layer for the real estate AI app. Upgraded from demo docs to a structured, inspectable, and retrieval-safe system.

---

## 1. Knowledge Architecture

### Document Categories (DocumentType)

| Type | Purpose |
|------|---------|
| `project_brochure` | Marketing brochures |
| `project_details` | Detailed project specs |
| `project_pdf` | Project PDFs (legacy) |
| `payment_plan` | Payment/installment plans |
| `faq` | Frequently asked questions |
| `sales_script` | Sales scripts |
| `support_sop` | Support standard operating procedures |
| `objection_handling` | Objection handling playbooks |
| `company_achievement` | Company achievements |
| `legal_compliance` | Legal and compliance docs |
| `achievement` | General achievement docs |
| `case_study` | Case studies |
| `delivery_history` | Delivery history |
| `project_metadata_csv` | Structured metadata import |
| `credibility` | Credibility content |
| `other` | Uncategorized |

### Document Metadata (IngestedDocument)

- `document_type` — Category above
- `source_of_truth` — Authoritative for its domain
- `version` — Version number
- `verification_status` — unverified | pending | verified | stale | superseded
- `validity_window_start` / `validity_window_end` — Temporal validity
- `last_verified_at` — When last verified
- `access_level` — public | internal | restricted

### Chunk Metadata (per-chunk, in `metadata` JSON)

- `document_type` — Propagated from document
- `verification_status` — Propagated from document
- `access_level` — Propagated from document
- `sub_index` / `total_subs` — For split chunks

### Retrieval Result Fields

- `chunk_id`, `content`, `chunk_type`, `section_title`
- `document_id`, `document_title`, `document_type`
- `source_of_truth`, `verification_status`, `access_level`
- `is_fresh` — Computed via RetrievalPolicy.is_fresh()
- `can_use_for_exact_pricing` — Always False (chunks never used for exact pricing)
- `can_use_for_exact_availability` — Always False

---

## 2. Design Choices

1. **Exact pricing/availability from Project only**  
   `RetrievalPolicy.can_use_for_exact_pricing( chunk )` and `can_use_for_exact_availability()` always return False. Structured pricing/availability come only from the Project model.

2. **Safe fallback language**  
   `get_safe_fallback_note( results, for_pricing=..., for_availability=... )` returns disclaimer text when answers rely on unverified document chunks or when pricing/availability is involved.

3. **Chunk metadata propagation**  
   Each chunk stores `document_type`, `verification_status`, `access_level` so retrieval and downstream logic can enforce policy without joining to the document.

4. **Freshness logic**  
   `RetrievalPolicy.is_fresh()` returns False for `verification_status=STALE`, for validity windows that ended, and for documents older than `max_stale_days` since `last_verified_at`.

5. **Access level**  
   Default is `internal`. Future retrieval can filter by `access_level` (e.g. public-only for unauthenticated users).

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `core/enums.py` | Added DocumentType members (project_brochure, project_details, payment_plan, sales_script, company_achievement, legal_compliance); added AccessLevel enum |
| `knowledge/models.py` | Added `access_level` to IngestedDocument |
| `knowledge/chunking.py` | Accept `verification_status`, `access_level`; add to chunk metadata |
| `knowledge/ingestion.py` | Pass doc metadata into chunk_document; set access_level on create |
| `knowledge/retrieval.py` | Added `access_level` to RetrievalResult; added `get_safe_fallback_note()`; fixed is_fresh order |
| `console/views.py` | Filters (document_type, access_level, verification_status); freshness per doc; retrieval test with fallback note |
| `console/templates/console/knowledge.html` | Filter controls; Access, Fresh, Version columns |
| `console/templates/console/knowledge_doc_detail.html` | Richer metadata; chunk retrieval meta; live retrieval test; fallback note |
| `knowledge/tests.py` | Chunk metadata test; retrieval access_level test; safe_fallback_note test; stale logic fix; skip pgvector tests on SQLite |

---

## 4. Migrations Created

- **knowledge/migrations/0003_knowledge_upgrade.py**  
  - Adds `access_level` (default `internal`) to IngestedDocument  
  - Extends `document_type` choices for IngestedDocument and RawDocument  

---

## 5. Tests Added/Updated

| Test | Purpose |
|------|---------|
| `test_chunk_metadata_propagates_on_ingestion` | Chunk metadata includes document_type, verification_status, access_level |
| `test_retrieval_result_has_access_level` | RetrievalResult has access_level (skipped on SQLite) |
| `test_safe_fallback_note_for_unverified` | get_safe_fallback_note returns disclaimer for pricing/unverified |
| `test_stale_knowledge_handling` | Fix: is_fresh returns False for STALE status (logic order fixed) |
| Retrieval tests | Skip when using SQLite (pgvector requires PostgreSQL) |

---

## 6. Console Changes

- **Knowledge list**  
  - Filters: document_type, access_level, verification_status  
  - Columns: Access, Fresh (✓/○), Version  
  - Retrieval policy note  

- **Document detail**  
  - Metadata: Access, Fresh, Version, Project  
  - Retrieval safety note  
  - Chunk metadata: document_type, verification_status, access_level  
  - Live retrieval test: enter query, see top matches + fallback note when applicable  

---

## 7. Verification Steps

1. Run migrations: `python manage.py migrate knowledge`
2. Run tests: `pytest knowledge/tests.py -v`
3. Open `/console/knowledge/` and confirm filters and new columns
4. Open a document and run retrieval test with a query; confirm fallback note when unverified
5. Verify chunk metadata in document detail page

---

## 8. Risks & Follow-up

| Risk | Mitigation / Follow-up |
|------|------------------------|
| Existing docs may have old `document_type` values | Migration keeps all existing values; new types are additive |
| SQLite tests skip retrieval | Use PostgreSQL for full retrieval tests in CI |
| access_level filtering not yet enforced in retrieval | Add optional `access_level` filter to `retrieve()` when needed |
| Orchestration doesn’t yet use get_safe_fallback_note | Call `get_safe_fallback_note()` before or in response generation when using document chunks for pricing/availability |
| Real company docs may need batch reclassification | Add management command or admin UI to set document_type, access_level, verification_status in bulk |
