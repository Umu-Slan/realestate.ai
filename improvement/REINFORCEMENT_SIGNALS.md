# Reinforcement Signals Layer

Structured outcome signals for improving AI sales behavior over time.

## Signal Types

| Signal | Description |
|--------|-------------|
| `user_continued_conversation` | User sent another message (re-engagement) |
| `user_requested_visit` | User asked to schedule a site visit |
| `user_asked_for_agent` | User requested human agent |
| `user_disengaged` | User stopped replying (inferred after timeout) |
| `objection_unresolved` | Objection was raised but not resolved |
| `recommendation_clicked_accepted` | User clicked/accepted a recommendation |
| `support_escalation` | Conversation escalated to support |
| `human_correction` | Operator corrected the AI response |

## Recording Signals

```python
from improvement.services.reinforcement_signals import record_reinforcement_signal

record_reinforcement_signal(
    "user_requested_visit",
    conversation_id=conv.id,
    customer_id=cust.id,
    journey_stage="shortlisting",
    strategy="convert",
    intent_primary="schedule_visit",
)
```

## Integration Points

- **Orchestration persistence**: After persisting a run, call `record_reinforcement_signal` for:
  - `user_continued_conversation` when user sends a follow-up message
  - `user_requested_visit` when intent is schedule_visit
  - `user_asked_for_agent` when routing is escalate_to_human
- **Support engine**: `support_escalation` when escalation occurs
- **Corrections**: `human_correction` when HumanCorrection or ResponseFeedback(is_good=False) is created
- **Recommendation UI**: `recommendation_clicked_accepted` when user clicks a recommended project
- **Disengagement job**: `user_disengaged` from a scheduled job that detects no reply for N hours

## Links

Each signal links to: conversation, customer, recommendation (optional), message (optional), journey_stage, strategy, intent_primary.

## Improvement Insights

Run "Refresh Insights" on `/console/improvement/` to aggregate reinforcement signals into ImprovementSignal. Signals appear as `issue_type=reinforcement_outcome`.
