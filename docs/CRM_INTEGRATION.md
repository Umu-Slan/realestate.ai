# CRM Integration — Architecture

## Import Architecture

```
CRM Export (CSV/Excel) → Adapter (CSVCRMAdapter / ExcelCRMAdapter)
    → Normalize fields → Validate → Identity Resolution
    → Create/Update: CustomerIdentity, Customer, LeadProfile, CRMRecord
    → CRMImportBatch (audit)
```

### Adapter Interface

- `BaseCRMAdapter`: `iter_leads(path)` yields `CRMLeadRow`
- Column mapping: flexible aliases (lead_name→name, mobile→phone, etc.)
- v0: CSV, Excel. Future: HubSpot, Salesforce via same interface

### Field Mapping

| Internal | External aliases |
|----------|------------------|
| crm_id | id, lead_id, external_id |
| name | lead_name, full_name, contact_name |
| phone | mobile, tel, phone_number |
| email | email_address, mail |
| source, campaign | lead_source, utm_campaign |
| historical_classification | classification, type, qualification |
| project_interest | project, interested_project |

---

## Identity Resolution

### Scoring Logic

| Signal | Score | Notes |
|--------|-------|-------|
| Exact external_id | 1.0 | Auto-match |
| Exact phone (9+ digits normalized) | 0.9 | |
| Exact email | 0.9 | |
| Username in metadata | 0.85 | |
| external_id = username | 0.9 | |
| Name similarity ≥0.8 | +0.1 | Boost |
| Name similarity <0.3 | -0.2 | Penalty |
| Conflicting email on other identity | -0.3 | |

### Output

- **matched**: bool
- **identity**: CustomerIdentity (or new when manual review)
- **confidence_score**: 0–1
- **match_reasons**: list[str]
- **manual_review_required**: true when 0.5 ≤ confidence < auto_merge_threshold (default 0.95)

### Merge Flow

- **Auto** (confidence ≥ 0.95): use existing identity
- **Manual** (0.5 ≤ c < 0.95): create new identity + IdentityMergeCandidate
- **Reject** (c < 0.5): create new identity, no candidate

---

## Unified Memory

- **Short-term**: Current conversation messages (fetched in timeline)
- **Long-term**: CustomerMemory (preference, past_intent, past_project, old_objection, prior_classification, support_history)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/crm/import/` | Import CRM file |
| GET | `/api/crm/import/summary/` | List import batches |
| GET | `/api/leads/search/?q=...` | Search customers |
| GET | `/api/leads/profile/<id>/` | Unified profile + timeline |
| GET | `/api/leads/identity/candidates/` | Pending merge candidates |
| POST | `/api/leads/identity/merge/<id>/approve/` | Approve merge |
| POST | `/api/leads/identity/merge/<id>/reject/` | Reject merge |
| POST | `/api/crm/events/` | Inbound lead upsert from company CRM (webhook; see below) |

### Bidirectional CRM with the company stack

**Historical + incoming data (into this platform)**  
- Bulk: `POST /api/crm/import/` (CSV/Excel) as today.  
- Streaming / real time: `POST /api/crm/events/` with JSON body (`crm_id` required; `phone`/`email`/`username` per row validation). Set `CRM_INBOUND_WEBHOOK_SECRET` in `.env` and send `Authorization: Bearer <secret>` or `X-Webhook-Secret: <secret>`. If the secret is unset, only `DEBUG=True` accepts traffic (unsafe for production).

**AI outcomes (out to the company CRM / middleware)**  
After each conversation sync, internal `CRMRecord` is updated as today. Optionally notify your system:  
- `EXTERNAL_CRM_PUSH_ENABLED=True`  
- `EXTERNAL_CRM_PUSH_MODE=webhook`  
- `EXTERNAL_CRM_WEBHOOK_URL=https://your-middleware.example/hooks/realestate-ai`  
- `EXTERNAL_CRM_WEBHOOK_SECRET` (optional Bearer on outbound POST)  

Payload shape: `{ "event": "ai_crm_sync", "crm_record_id", "record": { ...fields }, "delta": { ... } }`. Wire this URL to Zapier, n8n, or a small service that calls HubSpot / Zoho / Dynamics APIs.

---

## Commands

```bash
python manage.py import_crm crm/fixtures/demo_leads.csv
python manage.py import_crm path/to/file.xlsx --dry-run
```

---

## Demo File

`crm/fixtures/demo_leads.csv` — 10 sample leads with AR/EN names, varied statuses.
