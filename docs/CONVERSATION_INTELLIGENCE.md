# Conversation Intelligence & Business Decision Layer

## Overview

For every incoming message, the system determines:
- **Who** the user is (new lead, existing customer, returning, broker, spam)
- **What** they want (intent classification)
- **What information is missing** (qualification extraction)
- **Hot/Warm/Cold** (deterministic scoring)
- **Where to route** (business routing rules)

## Classification Design

### Intent Categories (Multi-Label)

| Intent | Description |
|--------|-------------|
| property_purchase | Property purchase inquiry |
| investment_inquiry | Investment inquiry |
| project_inquiry | Project inquiry |
| price_inquiry | Price inquiry |
| location_inquiry | Location inquiry |
| installment_inquiry | Installment inquiry |
| brochure_request | Brochure request |
| schedule_visit | Schedule visit |
| support_complaint | Support complaint |
| contract_issue | Contract issue |
| maintenance_issue | Maintenance issue |
| delivery_inquiry | Delivery inquiry |
| general_support | General support |
| spam | Spam |
| broker_inquiry | Broker inquiry |
| other | Other |

### Support Categories (Existing Customers)

| Category | Description |
|----------|-------------|
| installment | Installment/payment |
| contract | Contract issue |
| maintenance | Maintenance issue |
| delivery | Delivery inquiry |
| complaint | Complaint |
| documentation | Documentation |
| general_support | General support |

### Lead Qualification Extraction

- budget_min, budget_max
- budget_clarity (explicit_range | approximate | none | unclear)
- location_preference
- project_preference
- property_type
- residence_vs_investment (residence | investment | both | unknown)
- payment_method (cash | installments | both | unknown)
- purchase_timeline
- financing_readiness (ready | exploring | not_ready | unknown)
- family_size
- urgency (immediate | soon | exploring | unknown)
- missing_fields

## Scoring Logic (Deterministic)

| Factor | Max Points |
|--------|------------|
| Budget clarity | 15 |
| Budget fit | 15 |
| Timeline urgency | 15 |
| Intent strength | 15 |
| Responsiveness/engagement | 10 |
| Project match | 10 |
| Financing readiness | 10 |
| Decision authority | 5 |
| Returning interest | 5 |
| **Total** | **100** |

### Temperature Thresholds

| Score | Temperature |
|-------|-------------|
| 80-100 | Hot |
| 55-79 | Warm |
| 30-54 | Cold |
| Below 30 | Nurture |

## Routing Rules (Deterministic)

| Condition | Action |
|-----------|--------|
| Spam likelihood high | Quarantine |
| Angry existing customer | Escalation-ready support case |
| Exact price unavailable + price inquiry | Safe response policy |
| Legal/contract issue | Support/legal handoff only |
| Score ≥ 80 + visit requested | Senior sales queue |
| Low confidence | Clarification or human review |
| Support intents | Support queue |
| Broker | Broker queue |

## API

### POST /api/intelligence/analyze/

Request:
```json
{
  "message_text": "I want a 3BR in New Cairo, budget 4M. Schedule visit?",
  "conversation_history": [{"role": "user", "content": "..."}],
  "customer_id": 1,
  "customer_type": "new_lead",
  "is_existing_customer": false,
  "is_returning_lead": false,
  "message_count": 2,
  "has_project_match": true,
  "is_angry": false,
  "exact_price_available": true,
  "use_llm": true
}
```

Response:
```json
{
  "customer_type": "new_lead",
  "intent": {
    "primary": "schedule_visit",
    "secondary": ["property_purchase"],
    "confidence": 0.85,
    "is_support": false,
    "is_spam": false,
    "is_broker": false
  },
  "qualification": { ... },
  "scoring": {
    "score": 82,
    "temperature": "hot",
    "confidence": "high",
    "reason_codes": [...],
    "missing_fields": [],
    "next_best_action": "Schedule site visit immediately",
    "recommended_route": "senior_sales"
  },
  "routing": {
    "route": "senior_sales",
    "queue": "senior_sales",
    "requires_human_review": false,
    "escalation_ready": false,
    "quarantine": false
  },
  "support_category": "",
  "is_ambiguous": false,
  "requires_clarification": false
}
```

## Usage

```python
from intelligence.services.pipeline import analyze_message

result = analyze_message(
    "عايز شقة في المعادي، الميزانية 3 مليون. أعمل معاينة إمتى؟",
    conversation_history=[...],
    customer_type="new_lead",
    use_llm=True,
)
print(result.scoring.temperature)  # hot/warm/cold/nurture
print(result.routing.route)
```

## LLM vs Deterministic

- **Intent / Qualification**: LLM-assisted when `OPENAI_API_KEY` is set; deterministic regex fallback otherwise
- **Scoring**: Always deterministic
- **Routing**: Always deterministic
