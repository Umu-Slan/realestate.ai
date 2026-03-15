# Business-Facing Conversation Engines

## Overview

Domain-aware, professional response systems for:
- **Sales** – project questions, qualification, objections, next action
- **Support** – calm, structured, escalate when needed
- **Recommendation** – matching projects to lead criteria

Tone: professional Egyptian real estate team, not generic chatbot.

## Engines

### Sales Conversation Engine

- Answers project questions
- Presents projects professionally
- Asks qualification questions
- Handles objections via library
- Moves toward next action (brochure, visit)
- Arabic + English

### Support Conversation Engine

- Calm, respectful, structured tone
- Categorizes issue
- Collects missing information
- Provides grounded procedural guidance
- Escalates sensitive cases (legal, contract)

### Recommendation Engine

- Top matching projects by: budget, location, purpose, property type, urgency
- Explains why each recommendation fits
- Fallback when data is partial
- Never fabricates; distinguishes verified vs general

## Objection Library

| Objection | Key |
|-----------|-----|
| Price too high | price_too_high |
| Location concern | location_concern |
| Trust/credibility | trust_credibility |
| Payment plan mismatch | payment_plan_mismatch |
| Investment uncertainty | investment_uncertainty |
| Waiting hesitation | waiting_hesitation |

## Template Modes

| Mode | Use Case |
|------|----------|
| hot_lead | Ready to buy, schedule visit |
| warm_lead | Some interest, qualify further |
| cold_lead | Early exploration |
| nurture_lead | Long-term nurture |
| existing_customer_support | Support inquiries |
| angry_customer | Frustrated, escalate |
| brochure_request | Brochure handoff |
| viewing_request | Site visit booking |
| returning_lead | Previous contact |

## Response Constraints

- Never fabricate exact prices, availability, unit numbers
- Never invent project features
- Never overpromise delivery or returns
- Clearly distinguish verified vs general information

## API Endpoints

### POST /api/engines/sales/

```json
{
  "message": "عايز شقة في المعادي",
  "mode": "warm_lead",
  "qualification": {"location_preference": "المعادي"},
  "conversation_history": []
}
```

### POST /api/engines/support/

```json
{
  "message": "ميناء القسط تأخر",
  "category": "installment",
  "is_angry": false
}
```

### POST /api/engines/recommend/

```json
{
  "budget_min": 1500000,
  "budget_max": 3000000,
  "location_preference": "New Cairo",
  "property_type": "apartment",
  "purpose": "residence",
  "urgency": "soon",
  "lang": "ar"
}
```

### GET /api/engines/templates/

Returns available template modes.

### POST /api/engines/objection/

```json
{"message": "غالي جداً"}
```

Returns `{ "detected": true, "key": "price_too_high", "response": "..." }`.

## Demo UI

Visit `/api/engines/demo/` for an interactive demo:
- Sales chat (hot/warm/cold/returning modes)
- Support chat (with angry-customer toggle)
- Recommendation (budget, location inputs)

## Test Instructions

```bash
DATABASE_URL=sqlite:///test.db pytest engines/tests.py -v
```
