# Egyptian Real Estate AI — v0 Demo Package

## What This Is

An **internal pilot** for an AI-powered operating system for real estate sales and support in Egypt. It is not a toy chatbot or hackathon prototype. It is a working system designed to:

- **Qualify leads** from Arabic and mixed-language conversations
- **Score and route** leads (hot/warm/cold) with explainable reason codes
- **Triage support** for existing customers
- **Ground answers** in company knowledge while keeping pricing and legal content safe
- **Escalate** to humans when appropriate
- **Provide operators** an inspectable console to review AI behavior

---

## What Problem It Solves

| Problem | How v0 Addresses It |
|---------|---------------------|
| Inconsistent lead handling | Deterministic scoring with reason codes; audit trail for every run |
| Risky AI responses | Guardrails block unverified prices, legal advice, delivery promises |
| Unclear routing | Explicit routing rules (sales/support/quarantine) with handoff summaries |
| Opaque AI decisions | Operator console shows intent, qualification, score, sources per message |
| Stale or wrong pricing | Structured Project model for exact pricing; chunks for descriptive content only |
| No evaluation baseline | 85 demo scenarios with expected outputs; evaluation runner and metrics |

---

## Supported Demo Capabilities

| Capability | Status |
|------------|--------|
| Lead intake (Arabic/English) | ✅ |
| Intent classification | ✅ |
| Qualification extraction (budget, location, property type) | ✅ |
| Lead scoring with reason codes | ✅ |
| Routing (sales, support, quarantine, broker) | ✅ |
| Knowledge-grounded response drafting | ✅ |
| Guardrail checks (pricing, legal, delivery) | ✅ |
| Escalation with handoff summary | ✅ |
| Operator console (conversations, customers, support, escalations, knowledge, audit, corrections) | ✅ |
| CRM import (CSV) with summary report | ✅ |
| Document ingestion (PDF, TXT, CSV) with chunking and embedding | ✅ |
| Demo scenario replay and evaluation | ✅ |
| Health endpoints | ✅ |

---

## What Is Mocked vs Real

| Component | Demo Mode | Live Mode |
|-----------|-----------|-----------|
| **LLM** | Mock (canned Arabic responses) | OpenAI gpt-4o-mini |
| **Embeddings** | May use mock or live | OpenAI text-embedding-3-small |
| **WhatsApp/Instagram** | Not integrated | Future adapter |
| **CRM** | API + CSV import | Same; future: vendor sync |
| **Conversations** | API + console | Same |
| **Identity resolution** | Real (DB lookup) | Real |
| **Scoring** | Real (deterministic) | Real |
| **Routing** | Real | Real |
| **Policy/guardrails** | Real | Real |

**To run with real LLM**: Set `DEMO_MODE=false` and `OPENAI_API_KEY` in `.env`. Scenario evaluation will use live classification and response drafting.

---

## How to Run It

### One-Command Start (Recommended)

```bash
python manage.py run_demo
```

This will:
1. Run migrations
2. Seed projects, customers, CRM leads
3. Create demo users (admin, operator, reviewer, demo)
4. Load demo scenarios
5. Load sample conversations with orchestration snapshots
6. Start the development server at http://localhost:8000

**Prerequisites**: PostgreSQL 14+ with pgvector, Python 3.11+, `.env` from `.env.example`.

Use `--no-server` to skip starting the server (e.g. for CI or when running server separately).

### Manual Steps

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: DATABASE_URL
psql -U postgres -c "CREATE DATABASE realestate_ai;"
psql -U postgres -d realestate_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
python manage.py migrate
python manage.py make_demo_ready
python manage.py load_demo_users
python manage.py load_demo_scenarios
python manage.py load_demo_data
python manage.py runserver
```

---

## Demo Credentials

| User | Password | Role | Use |
|------|----------|------|-----|
| admin | demo123! | Admin | Full access |
| operator | demo123! | Operator | Console, corrections |
| reviewer | demo123! | Reviewer | Read + approve |
| demo | demo123! | Read-only | Stakeholder walkthrough |

- **Admin**: http://localhost:8000/admin/
- **Operator Console**: http://localhost:8000/console/
- **Health**: http://localhost:8000/health/

---

## Demo Scenarios to Try

### In Operator Console → Demo Eval (`/console/demo/eval/`)

1. **Hot lead** (HL-001): "ميزانيتي ٤ مليون، عايز شقة ١٥٠ متر في القاهرة الجديدة، ممكن أعمل زيارة اليوم؟"  
   → Expect: hot temperature, schedule_visit intent

2. **Support case** (SC-001): "أنا عميل عندكم، محتاج أسأل عن دفعة التقسيط القادمة"  
   → Expect: support route, installment category

3. **Angry customer** (AC-001): "هذا غير مقبول! انتظرت ٣ أشهر ولم يرد أحد!"  
   → Expect: escalation required

4. **Spam** (SP-001): "اضغط هنا للفوز بجائزة مليون جنيه!!!!!"  
   → Expect: quarantine route

### In Conversations (`/console/conversations/`)

- Open a conversation seeded by `load_demo_data` to see messages, intent, score, qualification, action logs, and feedback buttons.

### In Demo Eval Replay

- Click any scenario name to **Run** and inspect: actual vs expected, final response, qualification extraction, policy decision.

### Run Full Evaluation

```bash
python manage.py run_demo_eval --no-llm
python manage.py print_demo_report --failed-only
```

---

## Known Limitations in v0

See [ROADMAP_AND_LIMITATIONS.md](ROADMAP_AND_LIMITATIONS.md) for an honest, professional list of current constraints and planned improvements.

---

## Future Roadmap (Short)

- Live WhatsApp and Instagram adapters
- True CRM vendor integration (Salesforce, HubSpot, etc.)
- Multi-country expansion (GCC, North Africa)
- Voice layer for phone and IVR
- Advanced analytics dashboard

---

## Sample Data for CRM Import

Use `demo/fixtures/sample_crm_import.csv` when demonstrating CRM import via API.

## Key Docs

- [Stakeholder Walkthrough](STAKEHOLDER_WALKTHROUGH.md) — Step-by-step demo script
- [Local Dev](LOCAL_DEV.md) — Setup and troubleshooting
- [ADR](ADR.md) — Architecture decisions
- [Demo Readiness Checklist](DEMO_READINESS_CHECKLIST.md) — Pre-demo checks
- [Roadmap & Limitations](ROADMAP_AND_LIMITATIONS.md) — Honest constraints and future plans
