# Evaluation and Demo Harness

## Overview

Evaluation and demo harness for the v0 real estate AI system. Enables testing, demonstration, and assessment before stakeholder review.

## Dataset Format

Scenarios are stored in `demo/fixtures/demo_scenarios.json`. Each scenario has:

```json
{
  "scenario_type": "new_lead|hot_lead|warm_lead|cold_lead|support_case|angry_customer|legal_case|spam|broker|ambiguous_identity",
  "name": "NL-001",
  "messages": [{"role": "user|assistant", "content": "..."}],
  "expected_customer_type": "new_lead",
  "expected_intent": "project_inquiry",
  "expected_temperature": "hot|warm|cold|nurture",
  "expected_support_category": "installment|contract|...",
  "expected_route": "sales|support|quarantine|broker",
  "expected_escalation": false,
  "expected_next_action": "share_brochure"
}
```

### Scenario Counts

| Type | Count |
|------|-------|
| New leads | 20 |
| Hot leads | 10 |
| Warm leads | 10 |
| Cold leads | 10 |
| Support cases | 10 |
| Angry customers | 5 |
| Legal/contract | 5 |
| Spam/fake | 5 |
| Broker/partner | 5 |
| Ambiguous identity | 5 |
| **Total** | **85** |

## Management Commands

### load_demo_scenarios

Load scenarios from fixture into database.

```bash
python manage.py load_demo_scenarios
python manage.py load_demo_scenarios --clear   # Clear first, then load
```

### run_demo_eval

Run full evaluation across all scenarios.

```bash
python manage.py run_demo_eval           # With LLM (slower, more accurate)
python manage.py run_demo_eval --no-llm  # Rule-based only (faster)
```

### print_demo_report

Print evaluation report.

```bash
python manage.py print_demo_report                    # Latest run
python manage.py print_demo_report eval_xxx            # By run_id
python manage.py print_demo_report --failed-only       # Only failed
python manage.py print_demo_report --confusion         # Confusion areas
```

## Evaluation Runner

- **Location**: `demo/eval_runner.py`
- **Flow**: For each scenario, runs orchestration on the last user message, compares actual vs expected.
- **Comparison**: Intent (with aliases), temperature, route, escalation, support category.
- **Output**: Per-scenario pass/fail, metrics, failures list.

## Metrics

| Metric | Description |
|--------|-------------|
| intent_accuracy | % of scenarios with correct intent |
| lead_temperature_agreement | % with correct temperature (hot/warm/cold/nurture) |
| escalation_correctness | % with correct escalation flag |
| support_category_accuracy | % support cases with correct category |
| route_accuracy | % with correct route (sales/support/quarantine/broker) |
| response_safety_failures | Count of guardrail violations |
| retrieval_usage_count | Scenarios where retrieval was used |

## Demo Mode UI

1. Go to `/console/demo/eval/`
2. Pick a scenario by type (e.g. Hot Lead > HL-001)
3. Click to replay (runs orchestration)
4. Inspect: actual output, expected vs actual, final response, qualification

Links:
- **Demo Eval**: `/console/demo/eval/`
- **Replay**: `/console/demo/replay/<scenario_id>?run=1`
- **Demo Scenarios**: `/console/demo/`

## Sales Evaluation Harness

A dedicated harness measures AI sales quality across 8 dimensions:
intent, qualification, stage, recommendation, objection, next_step, arabic_naturalness, repetition.

See [SALES_EVALUATION.md](SALES_EVALUATION.md) for full docs.

```bash
python manage.py load_sales_eval_scenarios
python manage.py run_sales_eval
```

- **Console**: `/console/sales-eval/`
- **Admin**: SalesEvalScenario, SalesEvalRun, SalesEvalResult

## Smoke Tests

```bash
pytest demo/tests.py evaluation/tests.py -v
```

Covers: ingestion, CRM import, scoring, orchestration, UI (dashboard, conversations, demo eval), load_demo_scenarios, eval_runner.

## Demo Instructions (Stakeholder Pilot)

1. **Load data**: `python manage.py load_demo_scenarios && python manage.py load_demo_data`
2. **Start server**: `python manage.py runserver`
3. **Dashboard**: Open `/console/` – overview, counts
4. **Demo Eval**: Open `/console/demo/eval/` – pick scenario, click to replay, show pipeline output
5. **Conversations**: Open `/console/conversations/` – click a conversation – show messages, intent, score, routing
6. **Run eval**: `python manage.py run_demo_eval --no-llm` – show metrics
7. **Report**: `python manage.py print_demo_report --failed-only` – show failure analysis

## Egypt-First, Bilingual

- Scenarios are primarily in Arabic (Egypt market)
- Mixed Arabic/English where typical (e.g. "Budget 5M EGP")
- Intent/route labels use English internally
