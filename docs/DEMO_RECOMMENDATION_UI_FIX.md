# Demo Chat Recommendation UI Fix Summary

## Root Causes

1. **Global recommendation panel stayed open** – A single `#project-cards` panel lived between the chat and input. `showProjectCards()` updated its content whenever new matches arrived, but the panel stayed visible across unrelated turns because it was never explicitly closed when the user sent a new message without matches.

2. **"View details" had no behavior** – Buttons were rendered without `data-project-id` or `onclick`, so nothing happened on click.

3. **Recommendations were not scoped to turns** – All recommendations were shown in one shared panel, so old suggestions stayed visible even when the conversation moved on.

4. **No state handling** – There was no per-message binding of recommendations or logic for when panels should show or hide.

## Files Changed

| File | Change |
|------|--------|
| `engines/views.py` | Added `project_detail(request, project_id)` API to return project JSON for the modal. |
| `engines/urls.py` | Added `path("project/<int:project_id>/", views.project_detail)`. |
| `engines/templates/engines/demo.html` | Refactored recommendation flow: global panel removed, message-scoped cards, project detail modal, View details wired. |
| `engines/tests.py` | Added `test_project_detail_returns_200_for_valid_project` and `test_project_detail_returns_404_for_invalid_project`. |

## How Recommendation State Was Fixed

1. **Message-scoped cards** – Each assistant message with `matches` renders its own block of recommendation cards directly under that reply, inside the message wrapper.
2. **No global panel** – The previous `#project-cards` section was removed. Cards are only rendered inside message blocks.
3. **Per-turn updates** – When a new turn has no matches, no new recommendation block is added. Old turns keep their cards as part of history.
4. **Single message wrapper** – Each message (avatar + bubble + optional rec block) is in a `.space-y-2` wrapper so cards are visually grouped with their reply.
5. **RTL alignment** – Cards use `ps-12` (padding-inline-start) for proper RTL layout.

## How "View details" Now Works

1. Each card’s button has `data-project-id` set from `m.project_id` or `m.id`.
2. On click, `openProjectModal(projectId)` is called.
3. The modal fetches `/api/engines/project/<id>/` and receives project data (name, location, pricing, payment plan, delivery).
4. That data is rendered inside the modal body.
5. The modal can be closed by clicking the overlay or the close button.

## New API: `GET /api/engines/project/<id>/`

- **Purpose:** Serve project details for the "View details" modal.
- **Auth:** Public, read-only.
- **Response:** JSON with `id`, `name`, `name_ar`, `location`, `property_types`, `price_min`, `price_max`, `availability_status`, and optional `pricing`, `payment_plan`, `delivery`, `unit_categories`.
- **Errors:** 404 when project does not exist or is inactive.

## Verification Steps

1. **Message-scoped recommendations**
   - Trigger a qualified flow (budget + location) or use "Suggested projects".
   - Confirm cards appear directly under the AI message that produced them.
   - Send a new message without recommendations.
   - Confirm no new cards appear and earlier cards stay with their original messages.

2. **"View details" action**
   - Open the demo, get recommendations (e.g., via "Suggested projects").
   - Click "عرض التفاصيل · View details" on a card.
   - Modal opens with project name, location, price, and other details.
   - Close via overlay or close button.

3. **Panel behavior**
   - No global floating recommendation panel.
   - Each recommendation block is tied to its AI reply.
   - Older blocks remain in history and do not replace or override each other.

4. **Tests**
   - Run: `pytest engines/tests.py::test_project_detail_returns_200_for_valid_project engines/tests.py::test_project_detail_returns_404_for_invalid_project -v`
