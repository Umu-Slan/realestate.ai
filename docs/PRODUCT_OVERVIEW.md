# Real Estate AI Operating System — Product Overview

**Version:** v0  
**Purpose:** Client-facing and operator-facing description of capabilities and usage.

---

## 1. What the System Does

The Real Estate AI Operating System is an AI-powered platform for Egyptian real estate companies. It handles:

- **Lead qualification** — Classifies incoming inquiries, extracts budget, location, property type, and urgency
- **Lead scoring** — Assigns hot/warm/cold temperature with explainable reason codes
- **Project recommendations** — Matches qualified leads to available projects based on criteria
- **Support triage** — Routes after-sale, warranty, and delivery inquiries; creates support cases
- **Escalation** — Hands off complex or sensitive cases to humans with a prepared summary
- **Knowledge-grounded answers** — Uses company documents (brochures, FAQs) while keeping pricing accurate via structured data
- **CRM integration** — Imports historical leads; syncs conversation outcomes back to CRM records

The system is designed for **internal pilot** use—not a toy chatbot. Every AI decision is auditable and correctable.

---

## 2. Supported Flows

| Flow | Description | Entry Points |
|------|-------------|--------------|
| **Lead inquiry** | New lead asks about projects, pricing, or availability | Web chat (`/api/engines/sales/`), WhatsApp webhook, orchestration API |
| **Project recommendation** | Lead receives tailored project matches | `/api/engines/recommend/` (budget, location, property type) |
| **Support request** | Existing customer asks about delivery, warranty, payments | `/api/engines/support/`, or routed from lead flow when intent = support |
| **Escalation** | Complex inquiry, complaint, or VIP flagged for human | Automatic when policy triggers; handoff summary prepared |
| **CRM sync** | Historical leads imported; conversation notes appended to CRM | Import: `/api/crm/import/` or Onboarding; Sync: automatic after each run |
| **Console inspection** | Operators review conversations, scores, support cases, escalations | `/console/` (all views) |

---

## 3. Operator Usage

Operators use the **Operator Console** (`/console/`) for day-to-day oversight.

### Dashboard
- Counts: conversations, customers, support cases, open escalations
- Metrics: top intents, support categories, escalation reasons
- Quick links to key areas

### Conversations
- List of recent conversations with message count
- **Detail view**: messages, intent, qualification (budget, location, property type), lead score with reason codes, escalation/support links, action logs
- **Feedback**: "Good" to approve a response; "Submit correction" to flag and correct errors

### Customers
- Customer list with identity (phone, email)
- **Detail view**: timeline (messages, CRM notes, scores, support cases, escalations, recommendations)

### Support Cases
- Queue of support cases with triage category, status, SLA
- Detail: conversation link, customer, category, notes

### Escalations
- Open escalations with reason, status, handoff summary
- Detail: conversation, customer, resolution notes

### Recommendations
- View project recommendations made to customers
- Filter by project, customer, date

### Knowledge
- Browse ingested documents (PDFs, FAQs, brochures)
- View metadata, verification status, chunk previews
- **Document detail**: run retrieval test queries

### Onboarding
- Upload documents (PDF, CSV, Excel, TXT, MD)
- Upload structured project CSV (name, location, price range, payment plans)
- Upload CRM export (CSV/Excel)
- Reindex documents to rebuild search embeddings
- Inspect batch status and item results

### Audit & Corrections
- **Audit**: System action log (orchestration, persistence, sync)
- **Corrections**: Submit human corrections; view recent corrections for model improvement

### Demo
- Demo scenarios and evaluation mode for testing flows

---

## 4. Admin Usage

Admins have full access plus configuration controls.

### Company Configuration (`/console/company/`)

View and edit company settings via **Django Admin** (`/admin/companies/company/`):

| Field | Purpose |
|-------|---------|
| Name, Slug | Company identifier |
| Support Email, Phone, Website | Contact details shown in responses |
| Primary Color, Logo URL | Branding (for future UI customization) |
| Tone Settings | Formality, default language, escalation preferences |
| Default Channel Settings | Enabled channels (web, whatsapp), default channel |
| Knowledge Namespace | For future multi-tenant partitioning |

### Django Admin (`/admin/`)

- **Users & groups**: Create operator accounts, assign staff status
- **Companies**: Edit company configuration
- **Projects**: Add/edit projects manually if not using CSV import
- **Knowledge**: Inspect IngestedDocument, DocumentChunk
- **All models**: Full CRUD for troubleshooting

### Operator Accounts

Create users in Django Admin, then assign a **UserProfile** with role:

| Role | Capabilities |
|------|--------------|
| **Admin** | Full access; Company config; create/edit operators |
| **Operator** | Console access; submit corrections; approve escalations |
| **Reviewer** | Console access; submit corrections; approve escalations |
| **Demo** | Read-only; cannot submit corrections or approve |

---

## 5. Onboarding Flow

First-time setup for a new company:

1. **Company settings** — Create/configure company in Django Admin
2. **Project data** — Upload structured CSV (projects, prices, payment plans) or add via Admin
3. **Knowledge docs** — Upload brochures, FAQs, support SOPs via Onboarding
4. **CRM import** — Upload CRM export (CSV/Excel) to load historical leads
5. **Operator accounts** — Create users and assign roles
6. **Verify** — Run sample conversations; check console for correct scoring and routing

See **[First Company Onboarding Checklist](FIRST_COMPANY_ONBOARDING_CHECKLIST.md)** for a step-by-step guide.

---

## 6. Channels

| Channel | Status | Notes |
|---------|--------|-------|
| **Web** | ✅ | API engines (sales, support, recommend); orchestration run |
| **WhatsApp** | ✅ | Webhook integration; requires WHATSAPP_VERIFY_TOKEN |
| **Instagram, Phone, Email** | 🔜 | Placeholder; future adapters |

---

## 7. Security & Compliance

- **Authentication**: Required for console and onboarding; session-based
- **Roles**: Admin, Operator, Reviewer, Demo with distinct permissions
- **API**: Engines (chat) are public for customer-facing integration; orchestration and CRM import require auth
- **Audit**: All orchestration and persistence events logged
- **Data**: Backups include DB and media; restore procedures documented
