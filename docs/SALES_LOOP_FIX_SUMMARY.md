# Sales Conversation Loop Fix — Summary

## Root Cause

**Primary bug:** `LeadQualificationAgent` built its output from the **extraction result** (current message only), not from the **merged qualification** (prior + current). So even when `_merge_prior_qualification` correctly merged budget and location from the database, the agent output used `result.budget_min`, `result.location_preference`, etc., instead of the merged values. Downstream agents (sales_strategy, conversation_plan, response_composer) thus received incomplete state and kept asking for budget/location.

**Secondary issues:**
- `ResponseDecisionAgent` (sales_strategy) did not have explicit guards against asking for fields that were already known.
- Sales chat used a secondary pipeline (`orchestration.pipeline.run_sales_pipeline`) by default instead of the canonical multi-agent pipeline.
- Conversation plan could suggest `ask_budget` even when budget was known if the CTA logic slipped.

## Architecture Used

Reused the existing multi-agent pipeline:

| Required Agent | Existing Implementation |
|----------------|--------------------------|
| IntentAgent | `orchestration.agents.intent_agent` |
| EntityExtractionAgent | Inside `lead_qualification` via `intelligence.services.qualification_extractor` + intent entities |
| ConversationMemoryAgent | `orchestration.agents.memory_agent` |
| LeadQualificationAgent | `orchestration.agents.lead_qualification_agent` |
| BuyerStageAgent | `orchestration.agents.journey_stage_agent` |
| ResponseDecisionAgent | `orchestration.agents.sales_strategy_agent` + `next_action.compute_next_best_action` |
| ResponseComposerAgent | `orchestration.agents.response_composer_agent` |

**Pipeline flow:** `run_canonical_pipeline` → `run_orchestration(use_multi_agent=True)` → `run_multi_agent_pipeline` → `DEFAULT_AGENT_PIPELINE`.

## Design Choices

1. **Output merged state:** LeadQualificationAgent now builds its output from the merged `qualification` dict instead of the raw extraction `result`.
2. **Explicit “never ask known” guards:** `_compute_recommended_cta` checks qualification and overrides CTA when budget, location, or property_type are already known.
3. **Single pipeline path:** Sales chat always uses `run_canonical_pipeline`, removing the alternate `run_sales_pipeline` path.
4. **Defensive conversation plan:** When `has_budget` and `has_location`, the plan always returns consultant-style text and never suggests asking for budget or location again.

## Files Changed

| File | Change |
|------|--------|
| `orchestration/agents/lead_qualification_agent.py` | Output uses merged `qualification` instead of extraction `result` for budget, location, property_type, project_preference, purpose, urgency. |
| `orchestration/agents/sales_strategy_agent.py` | Added explicit guards in `_compute_recommended_cta`: never return ask_budget if budget is known, never ask_location if location is known, never ask_property_type if property_type is known. |
| `orchestration/agents/conversation_plan_agent.py` | When `has_budget` and `has_location`, always return consultant-style suggestion first; do not suggest asking for budget/location. |
| `engines/views.py` | `sales_chat` always uses `run_canonical_pipeline`. Removed `use_pipeline` branching and `run_sales_pipeline`. |
| `orchestration/tests_sales_loop.py` | New test file for repeated-question prevention, memory merge, stage progression, Arabic qualification flow. |

## Migrations Created

None. Changes are in orchestration logic only, no schema updates.

## Tests Added

| Test | Purpose |
|------|---------|
| `test_qualification_output_uses_merged_state` | Ensures LeadQualificationAgent output reflects merged budget/location, not extraction only. |
| `test_response_decision_never_asks_known_budget` | When budget is present, CTA must not be ask_budget. |
| `test_response_decision_never_asks_known_location` | When location is present, CTA must not be ask_location. |
| `test_merge_prior_qualification_preserves_budget` | Prior LeadQualification is merged into current qualification. |
| `test_stage_advances_when_budget_location_known` | When budget and location are known, next action is RECOMMEND_PROJECT. |
| `test_arabic_qualification_flow_no_repeat` | Three-turn Arabic flow does not re-ask for budget or location. |

## Verification Steps

1. **Run tests:**
   ```bash
   pytest orchestration/tests_sales_loop.py -v
   ```

2. **Manual flow (demo chat):**
   - Turn 1: "عايز أشتري شقة" → AI asks for budget.
   - Turn 2: "حوالي 3 مليون" → AI asks for location (not budget again).
   - Turn 3: "في الشيخ زايد" → AI acknowledges and asks about ready vs under-construction, or presents projects (no re-asking for budget/location).

3. **Operator view:** Qualification and journey stage in `OrchestrationSnapshot` / persistence reflect merged state.

## Remaining Risks

1. **LLM variation:** Response composer still uses an LLM; it may sometimes ignore guidance and re-ask. The stronger conversation plan and guards reduce this risk.
2. **Persistence timing:** LeadQualification is written in `persist_orchestration_artifacts` after the run. Fast consecutive messages could theoretically miss prior data; in practice web latency makes this rare.
3. **Parallel pipeline:** `orchestration.pipeline.py` still exists but is unused for the sales endpoint. It could be deprecated or removed to avoid confusion.
