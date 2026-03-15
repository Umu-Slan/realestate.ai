# Architecture Decision Records

## ADR-001: Modular Monolith

**Context**: Need to ship a credible v0 pilot quickly while keeping boundaries clear for future extraction.

**Decision**: Use a modular monolith—single Django codebase with app boundaries. No microservices.

**Consequences**: Fast iteration, simpler deployment, single DB. Clear app folders (core, leads, orchestration, etc.) enable later extraction if needed.

---

## ADR-002: Orchestration Over Chat Completion

**Context**: Real estate requires intent, qualification, routing, and guardrails—not just LLM chat.

**Decision**: Explicit orchestration pipeline (intake → identity → intent → qualification → scoring → routing → retrieval → draft → policy → handoff). LLM used only for draft and classification.

**Consequences**: Deterministic routing, explainable scores, audit trail. More stages to maintain but predictable behavior.

---

## ADR-003: Egypt-First, Bilingual

**Context**: Target market is Egyptian real estate; Arabic primary, English common in mixed contexts.

**Decision**: Content and fallback messages in Arabic first. Internal labels in English. Support both in inputs.

**Consequences**: Better UX for Egyptian users. Some duplication in messages.

---

## ADR-004: Structured Pricing Over Chunks

**Context**: Exact prices and availability must be trustworthy—RAG chunks can be stale or wrong.

**Decision**: Exact pricing and availability come from Project (structured) only. Chunks used for descriptive content. Guardrails block unverified exact prices in responses.

**Consequences**: Safe pricing answers. Chunk retrieval can fail without breaking pipeline.

---

## ADR-005: Graceful Degradation

**Context**: Pilot must not crash on missing knowledge, LLM timeout, or malformed input.

**Decision**: Centralized resilience module with safe fallback messages. Every failure path returns a user-facing message. Acceptance criteria (audit, reason codes, handoff) enforced.

**Consequences**: Credible demo under failure. Operators see what failed in console.

---

## ADR-006: Correlation IDs for Tracing

**Context**: Need to trace a request across orchestration, audit, and logs.

**Decision**: Middleware injects X-Correlation-Id per request. Audit payloads include run_id, conversation_id, correlation_id.

**Consequences**: Easier debugging. No distributed tracing system required for v0.

---

## ADR-007: Role Model for Console

**Context**: Different stakeholders need different access (admin vs operator vs readonly demo).

**Decision**: UserProfile with role: admin, operator, reviewer, demo. Demo role is read-only for stakeholder walkthroughs.

**Consequences**: Safe to hand demo credentials. Future: enforce in views.
