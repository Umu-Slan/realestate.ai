# Red Team Attack Report

**Date:** 2025-03-09  
**Goal:** Break the system. Find weaknesses. Force failures. Fix them.  
**Constraint:** No architecture redesign; detect and fix only.

---

## 1. Weaknesses Discovered

| # | Weakness | Severity | Location |
|---|----------|----------|----------|
| 1 | **Decimal InvalidOperation** – `qualification_override` with `budget_min: "not-a-number"` caused `Decimal("not-a-number")` to raise, crashing recommendation mode | High | `orchestration/orchestrator.py` |
| 2 | **Invalid conversation_id/customer_id** – String or non-integer values (e.g. `"abc"`) passed to `Conversation.objects.filter(pk=...)` could raise `ValueError` in DB layer | Medium | `channels/adapters/web.py` |
| 3 | **Malformed conversation_history** – String or dict instead of list could cause `AttributeError` when engines iterate (e.g. `m.get("role")` on a character) | Medium | `orchestration/orchestrator.py` |

---

## 2. Attack Scenarios Executed

| Scenario | Payload / Method | Expected behavior |
|----------|------------------|-------------------|
| **Malformed messages** | `{"content": ""}`, `{"content": null}`, `{}`, `{"content": []}` | 400 or 422; no crash |
| **Extremely long** | `"x" * 100000` | Truncate at 10k; no crash |
| **Mixed Arabic/English** | "عايز شقة في New Cairo" | 200; valid response |
| **Nonsense** | "asdfghjkl", emoji-only | 200; no crash |
| **Repeated spam** | Same message 5× | 200 each; no loop |
| **Invalid JSON** | `"not json"` body | 400/422; no 500 |
| **Missing content** | `{"channel": "web"}` | 400 |
| **Invalid conversation_id** | `"not-a-number"`, `999999999` | 200; no crash |
| **Invalid budget override** | `{"budget_min": "not-a-number"}` | 200; no crash |
| **Malformed conversation_history** | `"string"`, `{}`, `123` | 200; no crash |
| **Empty message (direct)** | `run_orchestration("", ...)` | Failed with empty_content |
| **Concurrent requests** | 5 threads, same endpoint | Unique run_ids; no corruption |

---

## 3. Fixes Applied

| # | Fix | File |
|---|-----|------|
| 1 | Wrap `Decimal(str(qual["budget_min"]))` and `budget_max` in try/except for `ValueError`, `TypeError`, `InvalidOperation`; fallback to `None` | `orchestration/orchestrator.py` |
| 2 | Add `_safe_int()` in web adapter; coerce `conversation_id` and `customer_id` to `int` or `None` before passing to schema | `channels/adapters/web.py` |
| 3 | Normalize `conversation_history` at start of `run_orchestration`: if not list/tuple, use `[]`; ensure list before passing to engines | `orchestration/orchestrator.py` |
| 4 | Add `InvalidOperation` to persistence `Decimal` conversion except clause | `orchestration/persistence.py` |

---

## 4. Files Changed

| File | Changes |
|------|---------|
| `orchestration/orchestrator.py` | (1) Try/except for `budget_min`/`budget_max` Decimal conversion in recommendation block; (2) Normalize `conversation_history` to list at entry |
| `channels/adapters/web.py` | Add `_safe_int()`; coerce `conversation_id` and `customer_id` |
| `orchestration/persistence.py` | Add `InvalidOperation` to Decimal conversion except |

---

## 5. Remaining Risks

| Risk | Mitigation |
|------|------------|
| **Very large payload** | No explicit size limit on request body; consider `DATA_UPLOAD_MAX_MEMORY_SIZE` or middleware |
| **Conversation history with huge list** | No limit on list length; engines use `history[-6:]` but full list is still in memory |
| **Rapid-fire DoS** | No rate limiting; consider throttling in production |
| **DB connection exhaustion** | Concurrent requests share connection pool; monitor under load |
| **Recommendation with no projects** | Returns empty matches; already handled |
| **Console pages with missing data** | May show empty states; not tested in this round |

---

## 6. Test Suite Added

**File:** `orchestration/tests_redteam.py`

- `test_malformed_empty_content` – empty, whitespace, missing content
- `test_malformed_null_content` – content: null
- `test_malformed_non_string_content` – number, array, dict
- `test_extremely_long_message` – 100k chars
- `test_normalize_intake_long_truncates` – 50k truncates to 10k
- `test_mixed_ar_en` – Arabic + English
- `test_nonsense_text` – random chars, emoji
- `test_repeated_spam` – 5× same message
- `test_invalid_json_body` – non-JSON body
- `test_missing_content_field` – no content key
- `test_orchestrator_empty_content` – direct empty string
- `test_unsupported_chars` – control chars
- `test_emoji_heavy` – emoji in message
- `test_recommendation_empty_budget` – qualification_override {}
- `test_recommendation_invalid_budget` – budget_min: "not-a-number"
- `test_support_mode` – support response_mode
- `test_invalid_conversation_id` – non-existent ID
- `test_conversation_id_string` – "not-a-number"
- `test_malformed_conversation_history` – string, dict, int
- `test_concurrent_requests` – 5 threads
- `test_web_adapter_content_types` – number, None for content

---

## 7. Summary

Three exploitable weaknesses were found and fixed:

1. **Recommendation crash** on invalid budget override  
2. **Type errors** from non-integer `conversation_id`/`customer_id`  
3. **AttributeError** from malformed `conversation_history`

The red team test suite exercises malformed input, edge cases, and concurrency to reduce regression risk.
