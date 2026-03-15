# Real Estate AI System — Architecture (v0)

## Overview

Controlled, enterprise-oriented modular monolith for a real estate company in Egypt. Acts as lead intake, qualification, sales conversation, support triage, CRM routing, knowledge-grounded answering, and human handoff engine.

**Market**: Egypt | **Languages**: Arabic, Egyptian Arabic, MSA, English

---

## Design Principles

1. **Separation of concerns**: Language generation ≠ business decision logic
2. **Deterministic critical path**: Routing, guardrails, compliance use rules
3. **LLM roles**: Extraction, classification, summarization, response drafting
4. **Auditability**: All important actions logged with reasoning
5. **Explainability**: Why a lead was scored/routed is traceable
6. **Human-in-the-loop**: Operator review, correction, escalation

---

## Domain Model (Core Entities)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORE DOMAIN                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Lead ◄───────────────┬───────────────► Identity (resolved)                  │
│    │                  │                                                      │
│    │  leads_to        │  has_many                                            │
│    ▼                  ▼                                                      │
│  Conversation ◄───► Message ◄───► MessageEvent (audit)                        │
│    │                  │                                                      │
│    │  has_intent      │  has_classification                                  │
│    ▼                  ▼                                                      │
│  Intent ◄────────► Classification                                            │
│                                                                              │
│  LeadQualification (extracted, versioned)                                     │
│  LeadScore (computed, deterministic + explainable)                            │
│  RoutingDecision (hot/warm/cold, with reason)                                 │
│  Escalation (triggered, status, resolution)                                  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           KNOWLEDGE                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Document (PDF, metadata, ingestion state)                                   │
│  DocumentChunk (vectorized, pgvector embedding)                               │
│  KnowledgeSource (ref to project, case study, etc.)                          │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                           CRM / STRUCTURED                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CRMLead (imported, historical classification)                               │
│  Project (verified projects, exact availability)                             │
│  PriceRange (verified ranges, not exact unless structured)                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Map (Modular Monolith)

| Module | Purpose | Key Components |
|--------|---------|----------------|
| **core** | Shared models, base classes, utilities | BaseModel, audit mixins |
| **leads** | Lead entity, identity resolution, CRM import | Lead, Identity, CRMLeadImport |
| **conversations** | Unified conversation, messages, events | Conversation, Message, MessageEvent |
| **ingestion** | PDF/document pipeline | Document, DocumentChunk, ingestion tasks |
| **knowledge** | RAG, retrieval, grounding | Embedding service, retrieval service |
| **intent** | Intent classification | IntentClassifier, Intent model |
| **qualification** | Lead qualification extraction | QualificationExtractor, LeadQualification |
| **scoring** | Lead scoring (deterministic) | LeadScorer, rule engine |
| **routing** | Hot/warm/cold, CRM routing | RoutingEngine, RoutingDecision |
| **support** | Support triage, categorization | SupportClassifier, SupportCategory |
| **recommendation** | Recommendation logic | ProjectRecommender |
| **escalation** | Escalation workflow | EscalationEngine, Escalation |
| **generation** | LLM response drafting (no decisions) | ResponseGenerator, prompt templates |
| **audit** | Audit logs, explanation | AuditLog, ActionLog |
| **review_console** | Internal operator console | Review views, correction APIs |
| **demo** | Demo mode, sample data, eval harness | Fixtures, eval scripts |

---

## Workflows

### 1. Incoming Message Flow

```
Message In
  → Identity Resolution (new vs existing)
  → Intent Classification (LLM-assisted)
  → Lead Qualification Extraction (LLM)
  → Scoring (deterministic rules)
  → Routing Decision (hot/warm/cold)
  → Support Categorization (if support intent)
  → Knowledge Retrieval (if answering)
  → Response Generation (LLM draft, no decisions)
  → Guardrail Check (deterministic)
  → Message Out + Audit
```

### 2. Document Ingestion Flow

```
PDF Upload
  → Parse, chunk (overlap strategy)
  → Embed (pgvector)
  → Store chunks + metadata
  → Index by source type (project, case study, etc.)
```

### 3. CRM Import Flow

```
CRM Export (CSV/JSON)
  → Validate schema
  → Identity match/create
  → Import lead + historical classification
  → Backfill scoring (if needed)
```

### 4. Escalation Flow

```
Trigger (rule or operator)
  → Create Escalation record
  → Route to operator queue
  → Human resolution
  → Audit closure
```

---

## Contracts (Key Interfaces)

### LeadScorer (deterministic)

- **Input**: LeadQualification, Conversation summary
- **Output**: score (0–100), tier (hot/warm/cold), explanation (list of factors)
- **Rules**: Explicit, versioned, testable

### ResponseGenerator (LLM, no decisions)

- **Input**: Intent, context, retrieved knowledge, guardrails
- **Output**: Draft text only
- **Never**: Emits pricing, availability, routing decisions

### KnowledgeRetriever

- **Input**: Query, filters (source type, project)
- **Output**: Ranked chunks with scores
- **Guardrail**: Do not return unverified pricing as factual

---

## Failure Modes & Mitigations

| Failure | Mitigation |
|---------|------------|
| LLM hallucination on pricing | Never generate exact pricing from RAG; use verified Project/PriceRange only |
| Identity collision | Fuzzy match + manual review queue |
| Scoring drift | Rule versioning, eval harness |
| Escalation bottleneck | Operator queue, SLA tracking |
| Document ingestion failure | Retry, dead-letter, admin alert |

---

## Tech Stack

- **Django 5** + **Django REST Framework**
- **PostgreSQL** + **pgvector** (embeddings)
- **Redis** (cache, Celery broker)
- **Celery** (async tasks)
- **Adapter-ready**: LLM (OpenAI/vertex), Embedding (OpenAI/others) — mock for demo

---

## v0 Scope Summary

**In**: PDF ingestion, CRM import, conversation model, identity resolution, intent, qualification, scoring, routing, support categorization, recommendation, escalation, audit, operator console, demo dataset, eval harness, demo mode.

**Out**: Live voice, WhatsApp/Instagram integrations, multi-tenant, advanced ML pipelines, ERP integrations, uncontrolled autonomous actions.
