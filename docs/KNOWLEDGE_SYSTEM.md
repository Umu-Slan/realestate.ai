# Knowledge System — Architecture

## Overview

Hybrid knowledge layer for Egyptian real estate: PDF ingestion, structured metadata, business-aware chunking, pgvector embeddings, and retrieval with strict policy for exact pricing/availability.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  RawDocument → IngestedDocument → DocumentVersion                             │
│       ↓              ↓                                                      │
│  Parse (PDF/CSV/Excel/TXT) → Chunk (business-aware) → Embed → DocumentChunk  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        RETRIEVAL                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Query → Embed → Semantic Search (L2) + Metadata Filters + Freshness Rank    │
│       ↓                                                                      │
│  RetrievalResult[] (with can_use_for_exact_pricing = False always)            │
│                                                                              │
│  Exact pricing/availability → Project model only (structured source of truth) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Models

| Model | Purpose |
|-------|---------|
| **RawDocument** | Uploaded file record (path, hash, type) |
| **IngestedDocument** | Parsed document with tracking: document_type, source_name, source_of_truth, uploaded_at, parsed_at, version, language, verification_status, validity_window, last_verified_at |
| **DocumentVersion** | Version history of parsed content |
| **DocumentChunk** | Vectorized chunk with chunk_type, section_title, embedding |
| **Project** | Structured source of truth for pricing/availability |

---

## Chunking Strategy

Business-aware chunking by section type:

- **project_section** — General project info
- **payment_plan** — Payment plans, installments
- **amenities** — Pool, gym, security
- **location** — Location, transport
- **company_achievement** — Achievements, credentials
- **delivery_proof** — Delivery history, certificates
- **faq_topic** — FAQ Q&A
- **objection_topic** — Objection handling scripts
- **support_procedure** — SOP steps

Section detection uses header patterns (##, numbered, AR/EN keywords). Long sections are split with sentence-boundary overlap.

---

## Retrieval Policy

1. **Descriptive answers** — May use document chunks (project info, amenities, FAQ, objections).
2. **Exact prices** — Must use `Project` (structured). Chunks never `can_use_for_exact_pricing`.
3. **Exact availability** — Must use `Project`. Chunks never `can_use_for_exact_availability`.
4. **If structured verification is missing** — Answer must be safe and non-committal (e.g., "للمعلومات الدقيقة يرجى التواصل مع فريق المبيعات").

---

## Commands

```bash
# Ingest from file or directory
python manage.py ingest_documents path/to/file.pdf --type project_pdf --source "Company"
python manage.py ingest_documents path/to/dir/ --type faq --source "Support"

# Reindex (re-embed) all or specific documents
python manage.py reindex_knowledge
python manage.py reindex_knowledge --document-ids 1,2,3

# Mark stale documents (unverified for 90+ days)
python manage.py verify_knowledge_freshness --mark-stale-after-days 90
```

---

## API Endpoints

All require authentication.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/knowledge/documents/` | List documents |
| POST | `/api/knowledge/documents/ingest/` | Ingest (path or content) |
| POST | `/api/knowledge/documents/reindex/` | Reindex |
| GET | `/api/knowledge/documents/<id>/chunks/` | Inspect chunks |
| POST | `/api/knowledge/retrieval/test/` | Test retrieval |

---

## Test Instructions

```bash
pytest knowledge/tests.py -v
```

Tests cover: ingestion from content/file, versioning, retrieval, stale handling, missing document, structured pricing, retrieval policy.

---

## Demo Documents

- `knowledge/fixtures/demo_faq.txt` — FAQ (AR/EN)
- `knowledge/fixtures/demo_objection.txt` — Objection handling
- `knowledge/fixtures/demo_achievement.txt` — Achievements, delivery proof

```bash
python manage.py ingest_documents knowledge/fixtures/ --type faq --source demo
```
