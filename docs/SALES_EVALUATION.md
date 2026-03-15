# Sales Evaluation Harness

## Overview

The sales evaluation harness measures whether the multi-agent AI sales system is actually improving across 8 dimensions:

| Dimension | Description |
|-----------|-------------|
| **intent_accuracy** | Correct intent classification |
| **qualification_completeness** | Budget, location, property type extraction |
| **stage_accuracy** | Journey stage (awareness, consideration, shortlisting, etc.) |
| **recommendation_relevance** | Matched projects fit criteria |
| **objection_handling_quality** | Empathetic, addresses concern, offers options |
| **next_step_usefulness** | Concrete CTA (brochure, visit, call) |
| **arabic_naturalness** | Consultant-like Arabic phrasing |
| **repetition_score** | 1 − repetition rate (higher = less repetitive) |

## Setup

```bash
python manage.py load_sales_eval_scenarios
python manage.py load_sales_eval_scenarios --clear   # Clear and reload
```

## Running Evaluation

```bash
python manage.py run_sales_eval           # Full run with LLM
python manage.py run_sales_eval --no-llm  # Rule-based only (faster)
python manage.py run_sales_eval --no-save # Run without persisting
```

## Inspecting Results

### Console UI
- **Sales Eval**: `/console/sales-eval/`
- **Run Detail**: `/console/sales-eval/run/<run_id>/`

### Django Admin
- `SalesEvalScenario` — scenarios by category
- `SalesEvalRun` — runs with aggregate metrics
- `SalesEvalResult` — per-scenario scores and failures

### Fixture Format

`evaluation/fixtures/sales_eval_scenarios.json`:

```json
{
  "category": "intent|qualification|objection|follow_up|arabic|mixed",
  "name": "SE-INT-001",
  "messages": [{"role": "user", "content": "..."}],
  "expected_intent": "project_inquiry",
  "expected_qualification": {"budget_max": 3000000, "location_preference": "..."},
  "expected_objection_key": "price_too_high",
  "expected_next_action": "ask_budget",
  "expected_response_contains": ["فهمت"],
  "expected_response_excludes": ["كيف أستطيع"],
  "is_arabic_primary": true
}
```

## Scenario Categories

- **intent** — Intent classification
- **qualification** — Budget/location/property extraction
- **objection** — Objection handling (price, location, waiting, comparing)
- **follow_up** — Natural follow-up questions
- **arabic** — Arabic naturalness
- **mixed** — Multi-dimension (intent + qualification + stage + next_step)

## Interpreting Metrics

- Scores 0–1 per dimension; higher is better (except `repetition_rate`, where lower is better; we store `repetition_score = 1 - repetition_rate`).
- Pass/fail per scenario when all expected checks pass.
- Use trend over runs to verify improvements after prompt/agent changes.
