# Demo Chat Fix Summary – Multi-Agent Pipeline Behavior

## Root Causes

1. **Memory not persisted/reused**
   - `LeadQualification` was persisted after each run, but `LeadQualificationAgent` did not load prior qualification before extracting from the current message.
   - Budget and location from previous turns were lost when only the current message was used.

2. **CTA buttons exposed internal labels**
   - `recommended_cta` lived in the strategy output but was not added to `run.routing`.
   - Views used `scoring["next_best_action"]` (e.g. `"ask_budget: Budget not specified"`) when `recommended_cta` was missing.

3. **Stage not advancing**
   - `compute_next_best_action` required `temperature in ("warm", "hot")` before recommending projects.
   - Leads with budget+location but lower temperature stayed in qualification instead of moving to consideration.

4. **Recommendation matches not used in sales mode**
   - `run.recommendation_matches` was only set when `response_mode == "recommendation"`.
   - Sales mode runs produced matches but did not expose them to the demo UI.

5. **Response Composer re-asking**
   - With merged qualification, the context contained budget and location, but the conversation plan and prompts did not consistently enforce “never re-ask known fields.”

---

## Files Modified

| File | Change |
|------|--------|
| `orchestration/agents/lead_qualification_agent.py` | Added `_merge_prior_qualification()` to load latest `LeadQualification` and merge budget, location, property_type across turns. Recomputed `missing_fields` from merged data. |
| `orchestration/next_action.py` | Removed temperature condition for budget+location case so `RECOMMEND_PROJECT` is used whenever both are known. |
| `orchestration/multi_agent_runner.py` | 1) Added `recommended_cta` from strategy to `run.routing`. 2) Set `run.recommendation_matches` in sales mode when matches exist. |
| `engines/views.py` | `_to_customer_facing_next_step()` parses `action:reason` and uses `NEXT_STEP_LABELS` for Arabic labels. |
| `engines/templates.py` | Added guideline: when both budget and location are known, never re-ask and advance with consultant-style reply. |
| `orchestration/agents/conversation_plan_agent.py` | Added consultant-style guidance when `has_budget` and `has_location`: ask about ready vs under-construction, then present matching projects. |
| `engines/templates/engines/demo.html` | 1) Filter out internal labels (e.g. `action: reason`) from `next_step` before rendering. 2) Added quick actions for “ميزانيتي 3 مليون” and “في الشيخ زايد” for testing. |

---

## Memory Usage Fix

- **Before:** Each message used only the current extraction; prior budget/location were ignored.
- **After:** `_merge_prior_qualification()` loads the latest `LeadQualification` for the customer (and optionally conversation) and fills missing budget, location, property_type before scoring.
- **Flow:** Persistence runs after each run; on the next turn, prior qualification is loaded and merged.

---

## CTA Mapping Fix

- **Internal values → Arabic labels:**

  | Internal | Customer-facing (Arabic) |
  |----------|--------------------------|
  | `ask_budget` | ما الميزانية المناسبة لك؟ |
  | `ask_preferred_area` / `ask_location` | في أي منطقة تفضل السكن؟ |
  | `ask_property_type` | هل تبحث عن شقة أم فيلا؟ |
  | `recommend_project` / `recommend_projects` | عرض المشاريع المناسبة |

- **Implementation:** `_to_customer_facing_next_step()` strips the `: reason` part and looks up the action in `NEXT_STEP_LABELS`. Only the `label` and `action` are exposed to the UI.

---

## Stage Progression Fix

- **Before:** `RECOMMEND_PROJECT` only when `budget` and `location` not missing and `temperature in ("warm", "hot")`.
- **After:** As soon as both budget and location are known, return `RECOMMEND_PROJECT` regardless of temperature.

---

## Verification Steps

1. **Budget + location flow**
   - Send: `ميزانيتي 3 مليون` → response should ask for location (or similar).
   - Send: `في الشيخ زايد` → response should acknowledge both and use consultant-style language (e.g. “ميزانية 3 مليون في الشيخ زايد تفتح عدة خيارات جيدة…”).
   - No re-asking for budget or location.

2. **CTA buttons**
   - CTAs use Arabic labels like “ما الميزانية المناسبة لك؟”.
   - No internal strings such as `ask_budget: Budget not specified`.

3. **Project cards**
   - After providing budget and location, “مشاريع مقترحة” should show when matches exist.
   - `run.recommendation_matches` is populated in sales mode when qualified.

4. **Quick actions**
   - Use “My budget 3M” and “In Sheikh Zayed” to run through the flow quickly.
