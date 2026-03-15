# Sales Pipeline Architecture

## Pipeline Diagram

```
User message
    │
    ▼
┌─────────────────────┐
│   IntentAgent       │  → intent: buy_property | investment | ask_projects | schedule_visit | general_question
│   confidence: float │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ EntityExtraction   │  → budget, location, property_type, bedrooms, payment_type
│ Agent              │     (pattern + extraction)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ConversationMemory │  → Merge into state. Never erase previous values.
│ Agent              │     state = { intent, budget, location, property_type, stage, lead_score }
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ LeadScoringAgent   │  → +20 budget, +20 location, +10 property_type, +10 financing
│                    │     lead_temperature: cold | warm | hot
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RecommendationAgent│  → Trigger only when: intent==buy_property AND location AND budget
│                    │     filter_projects(location, budget)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ResponseComposer    │  → Combine intent, state, projects, lead_temp
│ Agent              │     Generate natural response (no internal instructions)
└──────────┬──────────┘
           │
           ▼
    Final reply
```

## Files

| File | Purpose |
|------|---------|
| `orchestration/pipeline.py` | Central orchestration: `run_sales_pipeline()`, agent chaining, logging |
| `orchestration/pipeline_agents.py` | IntentAgent, EntityExtractionAgent, ConversationMemoryAgent, LeadScoringAgent, RecommendationAgent, ResponseComposerAgent |
| `engines/views.py` | `sales_chat` uses `run_sales_pipeline` when `use_pipeline=true` |
| `engines/templates/engines/demo.html` | Debug panel: Intent, Budget, Location, Lead, Agents executed |
| `logs/pipeline.log` | Agent output logs |

## API Response

```json
{
  "response": "…",
  "state": {
    "intent": "buy_property",
    "budget": 3000000,
    "location": "الشيخ زايد",
    "property_type": null,
    "stage": "consideration",
    "lead_score": 50,
    "lead_temperature": "warm"
  },
  "matches": [...],
  "pipeline": {
    "intent": "buy_property",
    "agents_executed": 6,
    "agent_logs": ["IntentAgent -> buy_property", "EntityAgent -> budget=3000000.0 location= Sheikh zayed", ...]
  }
}
```

## Verification Steps

1. **Pipeline execution**: Send "ميزانيتي 3 مليون" → then "في الشيخ زايد" → verify intent, budget, location in debug panel.
2. **State persistence**: Confirm state is sent back on next message and merged (budget + location retained).
3. **Recommendations**: When buy_property + budget + location, verify projects returned.
4. **Logging**: Check `logs/pipeline.log` for agent entries.
5. **Debug panel**: Intent, Budget, Location, Lead, Agents executed visible.
