# Persistence Integrity Audit Report

**Date:** March 9, 2025  
**Scope:** Customer, CustomerIdentity, Conversation, Message, LeadScore, LeadQualification, Recommendation, SupportCase, Escalation, ActionLog (Audit)  
**Rules:** No new features, fix issues only

---

## 1. Persistence Audit Summary

| Model | Records Created When | Relations | Timestamps | Metadata | Console Access |
|-------|---------------------|-----------|------------|----------|----------------|
| **CustomerIdentity** | CRM import, demo/channel identity resolution | external_id unique | created_at, updated_at | metadata JSON | Via Customer.identity |
| **Customer** | Demo, channels, CRM import | identity (FK), company (FK, nullable) | created_at, updated_at | metadata JSON | customers, customer_detail |
| **Conversation** | Demo, channels | customer (FK), company (FK, nullable) | created_at, updated_at | metadata JSON | conversations, conversation_detail |
| **Message** | orchestration.service, conversations.service | conversation (FK) | created_at, updated_at | metadata JSON | Via conversation.messages |
| **LeadScore** | orchestration.persistence (lead-type) | customer (FK) | created_at, updated_at | explanation JSON | customer_detail, analytics |
| **LeadQualification** | orchestration.persistence (lead-type) | customer (FK), conversation_id (int), message_id (int) | created_at, updated_at | raw_extraction JSON | customer_detail |
| **Recommendation** | orchestration.persistence (recommendation matches) | customer (FK), conversation (FK), project (FK) | created_at, updated_at | metadata JSON | analytics |
| **SupportCase** | orchestration.persistence (support route) | customer (FK), conversation (FK), message_id (int), escalation (FK) | created_at, updated_at | metadata JSON | conversation_detail, customer_detail, analytics |
| **Escalation** | orchestration.persistence (escalation_ready) | customer (FK), conversation (FK) | created_at, updated_at | handoff_summary JSON | conversation_detail, customer_detail, analytics |
| **ActionLog** | audit.service, orchestration, CRM, knowledge | subject_type, subject_id (string refs) | created_at | payload JSON | conversation_detail |

**Note:** The system uses `ActionLog` for audit; there is no model named `AuditLog`.

---

## 2. Verification per Model

### Customer
- **Created when:** `get_or_create_demo_conversation`, `get_or_create_customer` (channels), CRM import
- **Relations:** identity (required for demo/channels), company (nullable)
- **Fix applied:** Demo persistence now sets company for new customers and conversations

### CustomerIdentity
- **Created when:** `get_or_create` on first contact (demo session key, external_id)
- **Relations:** One identity can have multiple Customers (per company)

### Conversation
- **Created when:** Demo (one per session), channels (one per active)
- **Fix applied:** Conversation now gets company from customer or default

### Message
- **Created when:** Every user/assistant message via orchestration.service or conversations.service
- **Relations:** conversation (FK) — always set
- **Metadata:** intent, intent_confidence, run_id, response_mode stored on user_msg and assistant_msg

### LeadScore
- **Created when:** orchestration.persistence when customer_type is lead-type and scoring has score
- **Relations:** customer (FK)

### LeadQualification
- **Created when:** orchestration.persistence when lead-type and qualification has budget/location/property
- **Schema note:** conversation_id and message_id are IntegerField (not FK) — orphan possible if conversation deleted; intentional for audit retention

### Recommendation
- **Created when:** orchestration.persistence when run.recommendation_matches has project_id
- **Relations:** customer (FK), conversation (FK), project (FK)

### SupportCase
- **Created when:** orchestration.persistence when route in (support, support_escalation, legal_handoff)
- **Relations:** customer (FK, nullable), conversation (FK, nullable), message_id (int), escalation (FK, nullable)
- **Schema note:** message_id is IntegerField — same pattern as LeadQualification

### Escalation
- **Created when:** orchestration.persistence when should_escalate and cust exists
- **Relations:** customer (FK required), conversation (FK nullable)
- **Metadata:** handoff_summary (JSON), notes (from AuditFieldsMixin)

### ActionLog
- **Created when:** orchestration (_log_stage), audit.service.log, CRM sync, knowledge ingest
- **Relations:** subject_type + subject_id (flexible references)

---

## 3. Schema Issues (No Migration Required)

| Issue | Severity | Notes |
|-------|----------|-------|
| LeadQualification.conversation_id, message_id as IntegerField | Low | Denormalized for reference; can orphan if conversation deleted; retained for audit |
| SupportCase.message_id as IntegerField | Low | Same pattern |
| Customer.identity nullable | Info | Some legacy/import paths may create without identity |
| SupportCase.customer, conversation nullable | Info | Allows triage before full resolution |

---

## 4. Issues Found and Fixed

| # | Issue | Fix |
|---|-------|-----|
| 1 | Demo Customer/Conversation created without company | Added get_default_company(); new Customers get company in defaults; Conversation gets customer.company or default |
| 2 | Persistence failure silently ignored | Added logging.getLogger().warning when persist_orchestration_artifacts raises |

---

## 5. Files Changed

| File | Change |
|------|--------|
| `engines/demo_persistence.py` | Added company resolution; Customer defaults include company; Conversation gets company |
| `orchestration/service.py` | Added logging on persistence failure (was silent pass) |

---

## 6. Migrations Created

**None.** All changes are code-only. Schema is unchanged.

---

## 7. Orphan and Duplicate Checks

| Check | Result |
|-------|--------|
| Orphan Messages | None — Message requires conversation (FK) |
| Orphan LeadScores | None — LeadScore requires customer (FK) |
| Orphan SupportCases | Possible if customer/conversation deleted — model allows null; acceptable for retention |
| Duplicate Conversations | Demo uses session demo_conversation_id; channels use active conversation filter |
| Orphan LeadQualification | Possible via conversation_id/message_id (int) if conversation deleted — by design |

---

## 8. Console View Data Access

| View | Models Queried | Verification |
|------|----------------|--------------|
| dashboard | Conversation, Customer, SupportCase, Escalation, analytics metrics | OK |
| conversation_detail | Conversation, Message, OrchestrationSnapshot, ResponseFeedback, LeadScore, LeadQualification, ActionLog, Escalation, SupportCase | OK |
| customer_detail | Customer, LeadScore, LeadQualification, Conversation, SupportCase, Escalation, CRMRecord | OK |
| analytics | OrchestrationSnapshot, SupportCase, Message, LeadScore, Escalation, Recommendation | OK |

All console views use correct relations; no missing data paths detected.

---

## 9. Verification Steps

1. **Demo flow:** `POST /api/engines/sales/` — verify Customer and Conversation have company_id when Company exists
2. **Persistence failure:** Trigger invalid state (e.g. invalid project_id in recommendation) — verify warning logged
3. **Console:** Open `/console/conversations/`, `/console/customers/` — verify no errors with company-linked records
