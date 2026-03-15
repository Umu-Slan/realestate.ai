# Complexity Audit Report

**Date:** 2025-03-09  
**Scope:** Audit for unnecessary complexity—dead code, duplicate utilities, unused imports, redundant models, legacy code.  
**Constraint:** No new features; simplify and remove where safe; preserve architecture.

---

## 1. Dead Code Found

| Item | Location | Resolution |
|------|----------|------------|
| `_temp_to_stage()` | `orchestration/orchestrator.py` | **Removed** – Defined but never called. Stage mapping handled by `orchestration.persistence._temperature_to_stage`. |
| `ResilienceContext` | `core/resilience.py` | **Removed** – Dataclass defined but never used anywhere in codebase. |
| `persist_score()` | `scoring/engine.py` | **Removed** – Defined but never called. Lead persistence done via orchestration persistence and intelligence pipeline. |
| `get_fallback_for` / `detect_contradictory_qualification` | `core/resilience.py` | Kept – Used by orchestrator and intelligence pipeline. |

---

## 2. Simplifications Applied

### 2.1 Centralized Language Detection

**Before:** Same logic duplicated in three places:
- `engines/views.py` → `_detect_lang()`
- `engines/sales_engine.py` → `_detect_language()`
- `engines/support_engine.py` → `_detect_language()`

**After:** Single utility `engines/lang_utils.detect_response_language()` used by all three. Reduces ~30 lines of duplicate code.

### 2.2 Unused Imports Removed

| File | Import removed |
|------|----------------|
| `engines/support_engine.py` | `typing.Optional` |
| `engines/sales_engine.py` | `typing.Optional` |
| `scoring/engine.py` | `LeadScore`, `decimal.Decimal` (after removing `persist_score`) |
| `core/resilience.py` | `dataclasses.dataclass` (after removing `ResilienceContext`) |

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `orchestration/orchestrator.py` | Removed unused `_temp_to_stage()` |
| `core/resilience.py` | Removed unused `ResilienceContext`, `dataclass` import |
| `scoring/engine.py` | Removed unused `persist_score()`, `LeadScore` import |
| `engines/lang_utils.py` | **New** – Shared `detect_response_language()` |
| `engines/views.py` | Use `detect_response_language` from lang_utils; removed `_detect_lang` |
| `engines/sales_engine.py` | Use `detect_response_language`; removed `_detect_language`, `Optional` import |
| `engines/support_engine.py` | Use `detect_response_language`; removed `_detect_language`, `Optional` import |

---

## 4. Remaining Complexity Risks

### 4.1 Dual Scoring Engines (Documented, Not Removed)

| Engine | Location | Used By | Notes |
|--------|----------|---------|-------|
| `scoring/engine.py` | `score_lead(customer, qualification)` | `scoring/tests.py` | Rules-based, deterministic. Legacy; main pipeline does not use it. |
| `intelligence/services/scoring_engine.py` | `score_lead(qualification, intent, ...)` | `intelligence/services/pipeline.py`, intelligence tests, demo | Full-featured scoring used by orchestration. |

**Risk:** Two different scoring implementations; possible confusion or divergence.  
**Recommendation:** Over time migrate `scoring/tests.py` to use intelligence scoring, then deprecate/remove `scoring/engine.py`. Not done in this audit to avoid breaking tests.

### 4.2 Potentially Unused Models (Not Removed)

| Model | Location | Status |
|-------|----------|--------|
| `AuditEvent` | `audit/models.py` | No writes found; only `ActionLog` used by `audit/service.py`. May be legacy. |
| `ProjectDocument` | `knowledge/models.py` | Docstring: "Legacy document linked to project. Prefer IngestedDocument." No app usage; only admin. `DocumentChunk` links to `IngestedDocument`. |

**Risk:** Dead models increase migration and schema complexity.  
**Recommendation:** If confirmed unused, add deprecation comments and plan migration to remove. Not removed here to avoid migration churn without explicit confirmation.

### 4.3 Temperature → Stage Mapping

- **Active implementation:** `orchestration/persistence.py` → `_temperature_to_stage()` ( maps `"hot"` → `"visit_planning"`).
- **Removed:** `orchestrator._temp_to_stage()` (had different mapping: `"hot"` → `"decision"`). It was dead; removal does not affect behavior.

### 4.4 Database Queries

Per `STABILITY_REPORT.md`: ORM usage uses `select_related`/`prefetch_related` where appropriate. No N+1 or unnecessary query risks were introduced by this audit.

---

## 5. Summary

| Metric | Count |
|--------|-------|
| Dead functions removed | 3 |
| Unused classes removed | 1 |
| Duplicate logic consolidated | 1 (language detection) |
| Unused imports removed | 4 |
| New shared utility file | 1 (`engines/lang_utils.py`) |
| Files modified | 7 |

**Architecture preserved.** Changes are limited to removal of dead code and consolidation of duplicated logic. No features added, no breaking API changes.
