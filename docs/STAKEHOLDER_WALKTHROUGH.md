# Stakeholder Demo Walkthrough

A step-by-step script for presenting the Egyptian Real Estate AI v0 system to internal stakeholders. Estimated time: 25–35 minutes.

---

## Before You Start

- [ ] Run `python manage.py run_demo` (or follow manual setup)
- [ ] Confirm `GET /health/` returns 200
- [ ] Log in as **operator** at http://localhost:8000/admin/ (or use console directly)
- [ ] Open Operator Console: http://localhost:8000/console/

---

## 1. Ingest Company Documents

**Goal**: Show that the system can ingest and index company knowledge.

**Steps**:
1. Log in as **admin** at http://localhost:8000/admin/
2. Use the Knowledge API or a prepared script. For API:
   - `POST /api/knowledge/documents/ingest/` (auth required)
   - Body: `{"content": "مشروع النخيل يقع في القاهرة الجديدة. يضم شقق وفلل. نطاق الأسعار من 2.5 إلى 8 مليون جنيه.", "document_type": "faq", "title": "مشروع النخيل - نظرة عامة", "source_name": "demo"}`
3. Or use the Knowledge section in Operator Console → **Knowledge** → inspect existing docs (seeded by `load_demo_data`)
4. Show **Knowledge** → click a document → metadata, verification status, chunk previews
5. **Retrieval test**: On document detail page, enter a query (e.g. "أسعار الشقق") to show chunk matching

**Talking point**: "We ingest project docs and FAQs. Exact prices come from structured Project data, not chunks, to avoid stale or wrong figures."

---

## 2. Import CRM Leads

**Goal**: Show CRM import and that every batch produces a summary report.

**Steps**:
1. Use the sample CSV: `demo/fixtures/sample_crm_import.csv` (or create one with headers: `crm_id,name,phone,email,source,notes,project_interest,status`)
2. POST to `/api/crm/import/` with file upload (auth required)
4. Show the response: `total_rows`, `imported`, `duplicates`, `errors`, `batch_id`
5. In Operator Console → **Customers**, show imported customers

**Talking point**: "Every import produces a summary. Malformed files return a clear error report instead of failing silently."

**Note**: If API is not convenient, mention that `make_demo_ready` already seeds 100 CRM leads—they appear in the customer list and timeline.

---

## 3. Open Operator Console

**Goal**: Introduce the internal operator interface.

**Steps**:
1. Open http://localhost:8000/console/
2. Walk through the nav: Conversations, Customers, Support Cases, Escalations, Recommendations, Knowledge, Audit Log, Corrections, Demo Scenarios
3. Show the **Dashboard** counts (conversations, customers, support cases, open escalations)

**Talking point**: "This is the internal control room—not the customer-facing chat. Operators can inspect everything the AI does."

---

## 4. Run a New Lead Scenario

**Goal**: Show a new lead flowing through the pipeline.

**Steps**:
1. Go to **Demo Eval** (http://localhost:8000/console/demo/eval/)
2. Under **New Lead**, click **NL-001** (or any) with "Run" (add `?run=1` to URL)
3. Or use **Engines Demo**: http://localhost:8000/api/engines/demo/ — send "مرحبا، أبحث عن شقة في القاهرة الجديدة"
4. Show the response and, if using Demo Eval, the **Actual Output** panel

**Talking point**: "The system classifies intent, extracts qualification, and produces a grounded response—all auditable."

---

## 5. Show Qualification Extraction

**Goal**: Show that budget, location, property type are extracted.

**Steps**:
1. In **Demo Eval**, run **HL-001**: "ميزانيتي ٤ مليون، عايز شقة ١٥٠ متر في القاهرة الجديدة، ممكن أعمل زيارة اليوم؟"
2. Open the **Qualification (extracted)** section
3. Point out: budget range, location, property type, urgency

**Talking point**: "We extract structured qualification so routing and scoring are explainable."

---

## 6. Show Scoring and Routing

**Goal**: Show lead score, temperature, reason codes, and route.

**Steps**:
1. Go to **Conversations** → open a conversation that has orchestration snapshots
2. Show the **Lead Score** panel: score, temperature, journey stage, reason codes
3. Show **Customer & Routing**: customer type, channel, route

**Talking point**: "Every scored lead has reason codes. Hot/warm/cold drives routing and next best action."

---

## 7. Show Recommendation

**Goal**: Show project recommendations tied to the lead.

**Steps**:
1. Go to **Recommendations**
2. Show the table: customer, project, rationale, rank
3. Click a customer and show **Customer Profile** → Timeline → recommendations in the timeline

**Talking point**: "Recommendations are linked to conversations and customers for traceability."

---

## 8. Show Support Case Scenario

**Goal**: Show support triage for existing customers.

**Steps**:
1. In **Demo Eval**, run **SC-003** (maintenance) or **SC-001** (installment)
2. Show: support route, support category (e.g. installment, maintenance)
3. Go to **Support Cases** → show the queue

**Talking point**: "When we detect support intent for an existing customer, we triage by category and route to support."

---

## 9. Show Escalation

**Goal**: Show when and how escalation works.

**Steps**:
1. In **Demo Eval**, run **AC-001** (angry customer) or **LC-001** (legal)
2. Show: escalation required, handoff summary
3. Go to **Escalations** → show the queue
4. Emphasize: every escalation includes a handoff summary for the human

**Talking point**: "We escalate when policy requires it—angry customers, legal questions—and always provide a handoff summary."

---

## 10. Show Audit Trail

**Goal**: Show that every run is auditable.

**Steps**:
1. Go to **Audit Log**
2. Show entries: orchestration_started, orchestration_stage, orchestration_completed
3. Point out run_id, conversation_id, correlation_id in payloads

**Talking point**: "Every orchestration run is logged. We can trace any decision back to a specific run and conversation."

---

## 11. Show Evaluation Report

**Goal**: Show that we evaluate the system against known scenarios.

**Steps**:
1. Run: `python manage.py run_demo_eval --no-llm`
2. Run: `python manage.py print_demo_report --failed-only`
3. Show metrics: intent accuracy, temperature agreement, route accuracy
4. Or show **Demo Eval** → Last Eval Run

**Talking point**: "We have 85 demo scenarios with expected outputs. We run evaluations to track quality over time."

---

## 12. Optional: Human Correction

**Goal**: Show human-in-the-loop for AI responses.

**Steps**:
1. Go to **Conversations** → open a conversation with assistant messages
2. Show **Good** and **Submit correction** on an assistant message
3. Go to **Corrections** → show the form and recent corrections table

**Talking point**: "Operators can mark responses as good or submit corrections. This feeds future model improvements."

---

## Closing

- Summarize: qualified leads, explainable scoring, guardrails, operator visibility, audit trail, evaluation
- Mention known limitations and roadmap (see ROADMAP_AND_LIMITATIONS.md)
- Invite questions on architecture, safety, or rollout
