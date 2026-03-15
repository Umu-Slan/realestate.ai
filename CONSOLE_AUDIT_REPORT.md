# Operator Console Reliability Audit Report

**Date:** March 9, 2025  
**Scope:** Dashboard, conversations, customers, recommendations, support cases, escalations, knowledge, corrections, audit logs  
**Rules:** No new features, fix issues only

---

## 1. Console Audit Summary

| Section | Data Loads | Queries | Relations | Pagination | Detail Pages | N+1 | Empty/Broken |
|---------|-----------|---------|-----------|------------|--------------|-----|--------------|
| **Dashboard** | ✓ | ✓ | — | — | — | ✓ | ✓ |
| **Conversations** | ✓ | ✓ | ✓ | Limit 50 | ✓ | **FIXED** | ✓ |
| **Customers** | ✓ | ✓ | ✓ | Limit 50 | ✓ | ✓ | ✓ |
| **Recommendations** | ✓ | ✓ | ✓ | Limit 100 | — | ✓ | ✓ |
| **Support Cases** | ✓ | ✓ | ✓ | Limit 100 | ✓ | ✓ | ✓ |
| **Escalations** | ✓ | ✓ | ✓ | Limit 100 | ✓ | ✓ | ✓ |
| **Knowledge** | ✓ | ✓ | ✓ | Limit 50 | ✓ | ✓ | ✓ |
| **Corrections** | ✓ | ✓ | ✓ | Limit 100 | — | ✓ | ✓ |
| **Audit Logs** | ✓ | ✓ | — | Limit 100 | — | ✓ | ✓ |

---

## 2. Problems Detected

| # | Section | Issue | Severity |
|---|---------|-------|----------|
| 1 | **Conversations** | N+1: `c.messages.count` caused 1 extra query per row (50 queries) | Medium |
| 2 | **Conversations** | `c.customer.identity` — AttributeError when identity is None | High |
| 3 | **conversation_detail** | snapshot_map could overwrite when multiple snapshots have message_id=None | Low |
| 4 | **customer_detail** | `customer.identity.external_id` — AttributeError when identity is None | High |
| 5 | **Customers** | `c.identity.name` — AttributeError when identity is None | High |
| 6 | **Support cases** | `c.customer.identity.name` — AttributeError when identity is None | High |
| 7 | **Escalations** | `e.customer.identity.name` — AttributeError when identity is None | High |
| 8 | **Recommendations** | `r.customer.identity.name` — AttributeError when identity is None | High |
| 9 | **Corrections** | HumanCorrection link used `c.conversation_id` when None — bad URL | Low |

---

## 3. Fixes Applied

| # | Issue | Fix |
|---|-------|-----|
| 1 | N+1 on messages.count | Use `annotate(message_count=Count("messages"))` and `c.message_count` in template |
| 2 | identity None in conversations list | Wrap in `{% if c.customer.identity %}...{% else %}—{% endif %}` |
| 3 | snapshot_map message_id=None | Exclude snapshots with `message_id is None` from snapshot_map |
| 4 | identity None in customer_detail | Wrap Identity block in `{% if customer.identity %}...{% else %}No identity linked{% endif %}` |
| 5 | identity None in customers list | Wrap in `{% if c.identity %}...{% else %}—{% endif %}` |
| 6 | identity None in support cases | Add identity check; fallback to customer.id |
| 7 | identity None in escalations | Add identity check; fallback to customer.id |
| 8 | identity None in recommendations | Add identity check; fallback to customer.id |
| 9 | Corrections link with null conversation | Use `c.conversation_id|default:c.message.conversation_id` for URL |

---

## 4. Files Changed

| File | Change |
|------|--------|
| `console/views.py` | Added `Count("messages")` annotate for conversations; excluded message_id=None from snapshot_map |
| `console/templates/console/conversations.html` | N+1 fix (message_count); identity None guard |
| `console/templates/console/customer_detail.html` | Identity None guard for Identity section |
| `console/templates/console/customers.html` | Identity None guard |
| `console/templates/console/support_cases.html` | Identity None guard for customer display |
| `console/templates/console/escalations.html` | Identity None guard for customer display |
| `console/templates/console/recommendations.html` | Identity None guard for customer display |
| `console/templates/console/corrections.html` | Conversation link fallback to message.conversation_id |

---

## 5. Verification Notes

- **Pagination:** All list views use slice limits (50 or 100); no page-number pagination. Limits prevent unbounded queries.
- **Detail pages:** conversation_detail, customer_detail, support_case_detail, escalation_detail, knowledge_doc_detail — all use select_related/prefetch_related appropriately.
- **Empty views:** All sections have `{% empty %}` or similar to handle no-data cases.
