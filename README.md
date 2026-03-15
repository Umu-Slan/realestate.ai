# Egyptian Real Estate AI Operating System — v0

Modular-monolith Django project for AI-powered lead qualification, sales conversation, support triage, and human handoff in Egyptian real estate. Designed as an **internal pilot**—not a toy chatbot or hackathon prototype.

**Demo package**: [Demo README](docs/DEMO_README.md) | [Stakeholder Walkthrough](docs/STAKEHOLDER_WALKTHROUGH.md) | [Limitations & Roadmap](docs/ROADMAP_AND_LIMITATIONS.md)

**Key docs**: [Local Dev](docs/LOCAL_DEV.md) | [Docker Local](docs/DOCKER_LOCAL.md) | [Deployment](DEPLOYMENT.md) | [Backup & Recovery](BACKUP_RECOVERY.md) | [Release Candidate](RELEASE_CANDIDATE_SUMMARY.md) | [ADR](docs/ADR.md) | [Demo Checklist](docs/DEMO_READINESS_CHECKLIST.md)

**Product & Onboarding**: [Product Overview](docs/PRODUCT_OVERVIEW.md) | [First Company Onboarding Checklist](docs/FIRST_COMPANY_ONBOARDING_CHECKLIST.md) | [Release Readiness](RELEASE_READINESS.md)

---

## Architecture

### Modular Monolith Structure

```
Realestate/
├── config/                 # Django settings, URLs, Celery
├── core/                   # Shared base, enums
├── accounts/               # User/operator accounts
├── crm/                    # CRM records import
├── conversations/          # Conversation, Message
├── knowledge/              # Project, ProjectDocument, KnowledgeChunk (RAG)
├── leads/                  # Customer, Identity, LeadProfile, Qualification, Score
├── support/                # SupportCase, Escalation
├── orchestration/         # Message flow orchestration (services)
├── scoring/                # Lead scoring logic
├── recommendations/        # Project recommendations
├── integrations/           # LLM, embedding adapters
├── audit/                  # ActionLog, AuditEvent, HumanCorrection
├── evaluation/             # Eval harness
└── demo/                   # Demo scenarios, fixtures
```

### App Responsibilities

| App | Responsibility |
|-----|----------------|
| **core** | Base models (TimestampedModel, AuditFieldsMixin), domain enums (CustomerType, LeadTemperature, IntentType, etc.) |
| **accounts** | Staff/operator accounts via Django Auth |
| **crm** | CRMRecord — imported historical leads with classification |
| **conversations** | Conversation, Message — unified chat model |
| **knowledge** | Project (verified), ProjectDocument, KnowledgeChunk (pgvector) |
| **leads** | CustomerIdentity, Customer, LeadProfile, LeadQualification, LeadScore |
| **support** | SupportCase (triage), Escalation (human handoff) |
| **orchestration** | Message flow: intent → qualification → scoring → routing |
| **scoring** | Deterministic lead scoring rules |
| **recommendations** | Recommendation (project suggestions) |
| **integrations** | LLM/embedding adapters (OpenAI, mocks) |
| **audit** | ActionLog, AuditEvent, HumanCorrection |
| **evaluation** | Eval harness, test cases |
| **demo** | DemoScenario, fixtures, make_demo_ready |

---

## Domain Model

### Key Entities

- **CustomerIdentity** — Resolved identity (phone, email, external_id). New vs existing customer detection.
- **Customer** — Central record. customer_type: new_lead | existing_customer | returning_lead | broker | spam | support_customer.
- **Conversation** — One per customer/channel session.
- **Message** — Role, content, intent, intent_confidence.
- **LeadProfile** — Lead-specific profile, project_interest.
- **LeadQualification** — Extracted budget, property_type, location, timeline.
- **LeadScore** — Score (0–100), temperature (hot/warm/cold), journey_stage, explanation.
- **Project** — Verified project with price_min/max, availability.
- **ProjectDocument** — PDF/document linked to project.
- **KnowledgeChunk** — Vectorized chunk (pgvector 1536d) for RAG.
- **SupportCase** — Triage category (after_sale, warranty, delivery, etc.).
- **Escalation** — Reason, status, resolution.
- **CRMRecord** — Historical classification from CRM import.
- **Recommendation** — Project recommended to customer.
- **ActionLog** / **AuditEvent** — Audit trail.
- **HumanCorrection** — Human-in-the-loop corrections.
- **DemoScenario** — Predefined demo conversations.

---

## Enums

| Enum | Values |
|------|--------|
| CustomerType | new_lead, existing_customer, returning_lead, broker, spam, support_customer |
| LeadTemperature | hot, warm, cold |
| BuyerJourneyStage | awareness, consideration, decision, purchase, post_purchase, unknown |
| IntentType | project_inquiry, pricing, availability, schedule_visit, support, general_info, spam, other |
| SupportCategory | after_sale, warranty, delivery, payment, documentation, complaint, general |
| EscalationReason | pricing_request, complex_inquiry, complaint, urgent, vip, manual |
| SourceChannel | web, whatsapp, instagram, phone, email, crm_import, api, demo |
| ConfidenceLevel | high, medium, low, unknown |

---

## Migrations Created

- `core.0001_initial` — No tables (abstract models only)
- `leads.0001_initial` — CustomerIdentity, Customer, LeadProfile, LeadQualification, LeadScore
- `crm.0001_initial` — CRMRecord
- `knowledge.0001_initial` — Project, ProjectDocument, KnowledgeChunk (pgvector)
- `conversations.0001_initial` — Conversation, Message
- `support.0001_initial` — SupportCase, Escalation
- `recommendations.0001_initial` — Recommendation
- `audit.0001_initial` — ActionLog, AuditEvent, HumanCorrection
- `demo.0001_initial` — DemoScenario

---

## One-Command Demo Start (Recommended: Docker)

```powershell
docker compose up -d
.venv\Scripts\activate
python manage.py wait_for_db
python manage.py migrate
python manage.py run_demo
```

First time: `copy .env.example .env` (no edits needed for Docker). No host PostgreSQL required. See [docs/DOCKER_LOCAL.md](docs/DOCKER_LOCAL.md). Or run `.\scripts\start-demo.ps1`.

## Manual Setup (Docker or Host PostgreSQL)

```powershell
# If using Docker:
docker compose up -d

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # Docker: no edits. Host: set DATABASE_URL
python manage.py check_local_setup
python manage.py migrate
python manage.py make_demo_ready
python manage.py load_demo_users
python manage.py load_demo_scenarios
python manage.py load_demo_data
python manage.py runserver
```

If `migrate` fails, run `python manage.py check_local_setup`. See [docs/DOCKER_LOCAL.md](docs/DOCKER_LOCAL.md) or [docs/POSTGRESQL_SETUP_WINDOWS.md](docs/POSTGRESQL_SETUP_WINDOWS.md).

Health: `GET /health/`

### Demo Credentials (from load_demo_users)

| User     | Password  | Role      |
|----------|-----------|-----------|
| admin    | demo123!  | Admin     |
| operator | demo123!  | Operator  |
| reviewer | demo123!  | Reviewer  |
| demo     | demo123!  | Read-only |

- **Admin URL**: http://localhost:8000/admin/
- **Operator Console**: http://localhost:8000/console/

Change passwords before external access.

---

## Seed Data (from make_demo_ready)

- **10 projects** — Palm Hills, Sheikh Zayed Residence, New Cairo Heights, etc.
- **25 demo customers** — Mixed customer_type, source_channel
- **100 historical CRM leads** — Mixed classifications (hot, warm, cold, qualified, etc.)
