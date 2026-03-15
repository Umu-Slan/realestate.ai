# Safety and Guardrail Audit Report

**Date:** 2025-03-08  
**Scope:** Audit safety and guardrail behavior for pricing, legal, internal info, and availability.  
**Constraint:** No new features; fix issues only; stability and correctness focus.

---

## 1. Safety Audit Summary

### Case 1: Exact pricing not verified in structured data

| Check | Status |
|-------|--------|
| Does not hallucinate prices | ✅ |
| Does not promise unavailable facts | ✅ |
| Escalates when needed | ✅ (safe fallback, no escalation for price) |
| Uses safe fallback language | ✅ |

**Mechanism:**
- `get_structured_pricing(project_id)` returns `is_verified` (from `knowledge/retrieval.py`, `knowledge/services/structured_facts.py`).
- Orchestrator sets `has_verified_pricing` only when `pricing.get("is_verified")` is true.
- For price inquiries without verified pricing: `run.routing["safe_response_policy"] = True` and optionally `run.routing["unavailable_data"] = True`.
- Policy engine: `ResponsePolicy.SAFE_ANSWER_MODE` or `UNAVAILABLE_DATA_MODE` → safe rewrite ("Pricing varies by unit…", "Please contact our sales team…").
- `check_guardrails()` detects unverified exact price patterns (e.g. "2,500,000 EGP") and triggers `UNVERIFIED_EXACT_PRICE` → rewrite to safe text.
- Sales engine receives `has_verified_pricing` and `retrieval_context` → instructed not to state exact prices when unverified.
- Generic LLM path receives `safe_instruction` when `safe_response_policy` or `unavailable_data` is set.

### Case 2: Legal / contract advice

| Check | Status |
|-------|--------|
| Does not give legal advice | ✅ |
| Does not promise validity/interpretation | ✅ |
| Escalates when needed | ✅ |
| Uses safe fallback language | ✅ |

**Mechanism:**
- `LEGAL_PATTERNS` detect legal/contract advice (e.g. "legal advice", "contract validity", "هل هذا العقد صحيح").
- `apply_policy_engine()`: `GuardrailViolation.LEGAL_ADVICE` → `allow_response=False`, `force_escalation=True`, `block_reason="Legal advice detected"`.
- Safe rewrite: "For contract and legal matters, please speak with our legal team. I'll connect you with a specialist."
- Routing `route == "legal_handoff"` → `ResponsePolicy.ESCALATION_MODE`.

### Case 3: Internal information

| Check | Status |
|-------|--------|
| Does not expose internal data | ✅ |
| Escalates or blocks when detected | ✅ |
| Uses safe fallback language | ✅ |

**Mechanism:**
- `INTERNAL_PATTERNS` detect internal/restricted info (e.g. "internal margin", "confidential", "staff only", "cost price").
- `GuardrailViolation.INTERNAL_ONLY_INFO` → `allow_response=False`, `block_reason="Internal information detected"`.
- Safe rewrite: "I can help with general project information. For specific details, please contact our team."

### Case 4: Availability not verified

| Check | Status |
|-------|--------|
| Does not hallucinate unit counts | ✅ |
| Does not promise unavailable facts | ✅ |
| Escalates when needed | ✅ (safe fallback) |
| Uses safe fallback language | ✅ |

**Mechanism:**
- `get_structured_availability(project_id)` returns `is_verified` (from `knowledge/retrieval.py`).
- Orchestrator fetches both pricing and availability; sets `has_verified_availability` when `avail.get("is_verified")` is true.
- Availability inquiry detected via: `"availability"` in intent primary, or keywords (e.g. متوفر, متبقى, وحدة متبقية, availability, units left, كم وحدة).
- For availability inquiries without verified data: `run.routing["unavailable_data"] = True`.
- Policy engine: `AVAILABILITY_PATTERNS` detect unverified exact availability → `UNVERIFIED_EXACT_AVAILABILITY` → rewrite ("Availability is updated regularly. Please contact our sales team…").
- `UNAVAILABLE_DATA_MODE` provides generic safe response when structured data is absent.

---

## 2. Fixes Applied

| # | Fix | Purpose |
|---|-----|---------|
| 1 | Pass `has_verified_pricing` and `retrieval_context` to sales engine | Instruct LLM not to state exact prices when not verified |
| 2 | Add `safe_instruction` to generic LLM system prompt when `safe_response_policy` or `unavailable_data` | Avoid stating exact prices/availability from unverified context |
| 3 | Call `get_structured_availability()` alongside `get_structured_pricing()` | Populate `has_verified_availability` for policy engine |
| 4 | Use `pricing.get("is_verified")` for `has_verified_pricing` | Only treat pricing as verified when structured facts mark it so |
| 5 | Detect `is_availability_inquiry` (intent + keywords) | Proactively set unavailable-data behavior for availability questions |
| 6 | Set `run.routing["unavailable_data"] = True` for availability inquiries without verified data | Apply unavailable-data safe behavior and fallback language |
| 7 | Set `run.routing["unavailable_data"] = True` on retrieval error / fallback | Fail-safe when retrieval fails |
| 8 | Set `run.routing["unavailable_data"] = True` when `use_structured_pricing` but pricing unverified for price inquiry | Project fact requested but unavailable |

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `orchestration/orchestrator.py` | (1) Import and call `get_structured_availability()`; (2) set `has_verified_pricing`/`has_verified_availability` from `is_verified`; (3) detect availability inquiry; (4) set `safe_response_policy` and `unavailable_data` routing flags; (5) pass `has_verified_pricing` and `retrieval_context` to sales engine; (6) add `safe_instruction` to generic LLM path |

---

## 4. Verification

- **Policy engine** (`orchestration/policy_engine.py`): `check_guardrails()`, `apply_policy_engine()` – unchanged; patterns and escalation logic already correct.
- **Structured facts** (`knowledge/retrieval.py`, `knowledge/services/structured_facts.py`): `get_structured_pricing` and `get_structured_availability` return `is_verified` – confirmed.
- **Guardrail tests** pass:
  - `test_guardrail_unverified_price`
  - `test_guardrail_legal_advice`
  - `test_guardrail_legal_contract_validity`
  - `test_guardrail_internal_info`
  - `test_guardrail_unverified_availability`
  - `test_policy_engine_unavailable_data_mode`
  - `test_policy_engine_unverified_pricing_request`
  - `test_policy_engine_legal_blocks_and_escalates`
  - `test_policy_engine_restricted_internal_info`

---

## 5. Conclusion

The safety and guardrail system is now correctly wired end-to-end:

- **Pricing**: Verified only from structured facts; unverified → safe fallback and no exact numbers.
- **Legal**: Detected and blocked; escalation with safe handoff.
- **Internal**: Detected and blocked; safe fallback message.
- **Availability**: Same pattern as pricing; verified only from structured facts; unverified → safe fallback.

All four cases avoid hallucination, avoid promising unavailable facts, escalate or block when appropriate, and use safe fallback language.
