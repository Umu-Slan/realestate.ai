# CRM Integration Foundation – Design

Foundation for real company onboarding. CSV/Excel import preserved; richer mapping; sync from conversation outcomes; adapter-friendly for external CRM.

---

## 1. CRM Layer Design

### Mapping Model (CRMRecord extended)

| Field | Purpose |
|-------|---------|
| **Contact** | external_phone, external_email, external_name, external_username |
| **Lead** | historical_classification, historical_score, status, project_interest |
| **Lead stage** | lead_stage (synced); historical_stage (import snapshot) |
| **Owner** | owner (sales rep) |
| **Tags** | tags (JSONField list) |
| **Notes** | notes (appendable) |
| **Support link** | support_case_id |

### New Models

| Model | Purpose |
|-------|---------|
| **CRMActivityLog** | Audit trail: note_added, stage_updated, owner_assigned, queue_assigned, support_linked |
| **CRMMapping** | Company-specific field mapping (source_type, mapping_config JSON) for future adapters |

### Sync Service API

- `get_or_create_crm_record_for_customer(customer_id, ...)` – create record for sync if none exists
- `append_note_to_crm(crm_record_id|customer_id, note, actor)` – append note, log activity
- `update_lead_stage(...)` – update lead_stage, log activity
- `assign_owner(...)` – assign owner
- `assign_queue(...)` – assign queue
- `link_support_case(...)` – link support case
- `sync_conversation_outcome(customer_id, note, lead_stage, owner, queue, actor)` – batch sync

---

## 2. Design Choices

1. **CSV/Excel unchanged** – New columns (owner, lead_stage, tags) mapped via COLUMN_ALIASES; optional.
2. **Sync creates record** – If no CRMRecord for customer, sync creates one (`sync_{customer_id}_{identity_id}`).
3. **Activity log per operation** – Each sync op creates CRMActivityLog + optional ActionLog.
4. **Orchestration hook** – After pipeline completes, `sync_conversation_outcome` called when conversation has customer and qualification data. Disable via `CRM_SYNC_ENABLED = False`.
5. **Adapter-friendly** – CRMMapping stores per-source config; BaseCRMAdapter interface unchanged; future Salesforce/HubSpot adapters can implement same interface.

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `crm/models.py` | CRMRecord: owner, assigned_queue, lead_stage, tags, support_case_id; CRMActivityLog; CRMMapping |
| `crm/adapters/base.py` | CRMLeadRow: owner, lead_stage, tags |
| `crm/adapters/csv_adapter.py` | COLUMN_ALIASES for owner, lead_stage, tags |
| `crm/adapters/excel_adapter.py` | Map owner, lead_stage, tags |
| `crm/services/import_service.py` | Populate owner, lead_stage, tags on create |
| `crm/services/sync_service.py` | New: full sync API |
| `crm/admin.py` | CRMActivityLog inline; CRMMapping, CRMActivityLog admin |
| `leads/services/timeline.py` | Include CRMActivityLog in timeline |
| `console/views.py` | Prefetch activity_logs for crm_records |
| `console/templates/console/customer_detail.html` | Richer CRM History: owner, stage, tags, activity logs |
| `orchestration/orchestrator.py` | CRM sync after pipeline (when CRM_SYNC_ENABLED) |
| `crm/tests.py` | Import with owner/tags; sync tests |

---

## 4. Migrations Created

- **crm/migrations/0003_crm_integration_foundation.py**
  - CRMRecord: owner, assigned_queue, lead_stage, tags, support_case_id
  - CRMActivityLog
  - CRMMapping

---

## 5. Tests Added/Updated

| Test | Purpose |
|------|---------|
| `test_import_with_owner_and_tags` | CSV import maps owner, lead_stage, tags |
| `test_sync_create_crm_record_for_customer` | Creates record and RECORD_CREATED activity |
| `test_append_note_to_crm` | Appends note and NOTE_ADDED activity |
| `test_update_lead_stage` | Updates stage and STAGE_UPDATED activity |
| `test_assign_owner_and_queue` | Owner and queue assignment |
| `test_sync_conversation_outcome` | Full sync: note, stage, owner |

---

## 6. Verification Steps

1. `python manage.py migrate crm`
2. `pytest crm/tests.py -v`
3. Import CSV with owner, lead_stage, tags columns – verify in admin
4. Run orchestration with conversation → check CRM record + activity log on customer detail
5. Open customer detail → CRM History shows owner, stage, tags, activity logs

---

## 7. Risks & Follow-up

| Risk | Mitigation / Follow-up |
|------|------------------------|
| Sync on every message | Only syncs when note_parts non-empty (qualification/scoring); disable via CRM_SYNC_ENABLED |
| Duplicate notes | append_note appends; no dedup. Add idempotency key in metadata if needed |
| External CRM push | Sync service writes to local CRMRecord; add outbound adapter (Salesforce API, webhook) later |
| CRMMapping unused | Placeholder for company-specific column mapping; use when onboarding second company |
