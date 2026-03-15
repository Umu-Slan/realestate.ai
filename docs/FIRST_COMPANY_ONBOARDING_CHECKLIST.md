# First Company Onboarding Checklist

**Purpose:** Step-by-step checklist for onboarding the first real estate company into the AI Operating System.  
**Audience:** Deployment team, company admins.  
**Estimate:** 2–4 hours depending on data volume.

---

## Prerequisites

- [ ] System deployed (Docker production or equivalent)
- [ ] Health check passes: `curl http://your-host/health/ready/`
- [ ] Admin account created (Django Admin or `load_demo_users` + change password)
- [ ] `.env` configured: SECRET_KEY, ALLOWED_HOSTS, OPENAI_API_KEY (if DEMO_MODE=false)

---

## 1. Company Settings

**Where:** Django Admin → Companies → Company (or first company created by migration)

| Task | Action | Notes |
|------|--------|-------|
| [ ] Set company name | Edit `name` field | e.g. "Acme Developments" |
| [ ] Set support email | Edit `support_email` | Used in support responses |
| [ ] Set support phone | Edit `support_phone` | Optional |
| [ ] Set website URL | Edit `website_url` | Optional |
| [ ] Set primary color | Edit `primary_color` | Hex e.g. `#1a365d` |
| [ ] Set tone settings | Edit `tone_settings` (JSON) | e.g. `{"formality": "professional", "default_lang": "ar"}` |
| [ ] Verify company is active | `is_active = True` | Required for default company |

**Optional:** Configure `default_channel_settings` for enabled channels (web, whatsapp).

---

## 2. Project Data (Pricing & Inventory)

**Where:** Operator Console → Onboarding → Upload Structured Data

| Task | Action | Notes |
|------|--------|-------|
| [ ] Prepare project CSV | Columns: name, location, price_min, price_max | See template below |
| [ ] Add payment plans (optional) | Columns: installment_years_min, down_payment_pct_min | Same CSV or separate |
| [ ] Upload via Onboarding | Choose "Structured CSV" or "Structured Excel" | CSV recommended |
| [ ] Verify batch result | Check batch detail for imported/skipped/failed | Fix any errors and re-upload |
| [ ] Confirm projects in Knowledge | Visit Knowledge → Structured Facts | Projects appear with pricing |

**Structured CSV template (columns):**
```csv
name,location,price_min,price_max,installment_years_min,down_payment_pct_min
Palm Hills,New Cairo,2500000,8000000,5,20
Sheikh Zayed Residence,6th October,1800000,4500000,7,15
```

**Alternative:** Add projects manually in Django Admin → Knowledge → Projects.

---

## 3. Knowledge Documents

**Where:** Operator Console → Onboarding → Upload Documents

| Task | Action | Notes |
|------|--------|-------|
| [ ] Prepare project brochures | PDF, TXT, MD | One or more per project |
| [ ] Prepare FAQs | PDF or TXT | document_type = faq |
| [ ] Prepare support SOPs (optional) | PDF or TXT | document_type = support_sop |
| [ ] Upload documents | Select files, choose document type, optionally link to project | Max 10MB per file (default) |
| [ ] Verify ingestion | Check batch detail; visit Knowledge → Documents | Each file creates IngestedDocument + chunks |
| [ ] Run retrieval test | Document detail → enter query | Ensure chunks match expected content |
| [ ] Reindex if needed | Onboarding → Reindex Documents | After bulk changes |

**Supported formats:** PDF, CSV, Excel (.xlsx, .xls), TXT, MD.

---

## 4. Pricing & Inventory Truth

**Source of truth:** Structured Project data (from step 2), not document text.

| Task | Action | Notes |
|------|--------|-------|
| [ ] Ensure Project records have price_min, price_max | From structured CSV or Admin | AI uses these for exact pricing |
| [ ] Mark document as "Source of truth" if appropriate | On upload form | Affects verification workflow |
| [ ] Verify Structured Facts page | Console → Structured Facts | Shows project pricing and payment plans |

The system blocks unverified price quotes in responses. Structured Project data is the authoritative source.

---

## 5. CRM Import & Sync

**Where:** Operator Console → Onboarding → Upload CRM, or API `POST /api/crm/import/`

| Task | Action | Notes |
|------|--------|-------|
| [ ] Export CRM data | CSV or Excel | Columns: crm_id, name, phone, email, source, notes, project_interest, status |
| [ ] Upload via Onboarding | Choose CRM file | Creates CRMRecord per row; links to Customer if identity matches |
| [ ] Verify import summary | Batch detail: imported, duplicates, errors | Fix malformed rows and re-import if needed |
| [ ] Confirm in Customers | Console → Customers | Imported leads appear with CRM history |
| [ ] Enable sync (default on) | `CRM_SYNC_ENABLED=True` in settings | Conversation outcomes appended to CRM records |

**CRM CSV template:**
```csv
crm_id,name,phone,email,source,notes,project_interest,status
CRM001,Ahmed Ali,+201234567890,ahmed@example.com,website,Interested in New Cairo,New Cairo Heights,qualified
```

---

## 6. Operator Accounts

**Where:** Django Admin → Authentication and Authorization → Users

| Task | Action | Notes |
|------|--------|-------|
| [ ] Create admin user | Add user, set password, Staff = True, Superuser = True (or assign admin group) | Company config access |
| [ ] Create operator users | Add user, Staff = True; create UserProfile with role = OPERATOR | Day-to-day console access |
| [ ] Create reviewer (optional) | UserProfile with role = REVIEWER | Can approve escalations |
| [ ] Create demo (optional) | UserProfile with role = DEMO | Read-only for demos |
| [ ] Change default passwords | If using load_demo_users | admin, operator, reviewer, demo all use demo123! initially |

**Profile creation:** After creating a User, go to User Profiles (or accounts app) and create a profile with the appropriate role.

---

## 7. Verification

| Task | Action | Expected |
|------|--------|----------|
| [ ] Run sample lead | POST `/api/engines/sales/` with `{"message": "أبحث عن شقة في القاهرة الجديدة، ميزانيتي ٣ مليون"}` | JSON with `response` |
| [ ] Run recommendation | POST `/api/engines/recommend/` with budget/location | Project matches returned |
| [ ] Inspect conversation | Console → Conversations → open latest | Intent, qualification, score visible |
| [ ] Check support routing | POST support-style message | SupportCase created; visible in Support queue |
| [ ] Verify CRM link | After lead flow, check Customer → CRM history | Notes appended if CRM record exists |
| [ ] Test onboarding uploads | Re-run document upload with small file | Batch completes; Knowledge updated |

---

## 8. Go-Live Checklist

- [ ] All operator passwords changed from defaults
- [ ] Company settings reviewed and correct
- [ ] At least one project with pricing loaded
- [ ] Knowledge documents ingested for main projects
- [ ] CRM import completed (if historical data exists)
- [ ] Sample conversations verified
- [ ] Backup scheduled (see BACKUP_RECOVERY.md)
- [ ] HTTPS and reverse proxy configured (if production)
- [ ] CSRF_TRUSTED_ORIGINS set (if HTTPS)

---

## Reference Links

| Doc | Purpose |
|-----|---------|
| [Product Overview](PRODUCT_OVERVIEW.md) | What the system does; operator/admin usage |
| [Deployment](../DEPLOYMENT.md) | Production deployment guide |
| [Backup & Recovery](../BACKUP_RECOVERY.md) | Backup procedures |
| [Release Readiness](../RELEASE_READINESS.md) | Internal release readiness summary |
