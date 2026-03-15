# SaaS UI/UX Upgrade

Production-grade SaaS interface for the Real Estate AI Operator Console.

## 1. Application Layout

**File:** `console/templates/console/base.html`

- **Left sidebar (240px):** Persistent navigation with sections
  - Dashboard
  - Engagement: Conversations, Customers, Leads, Recommendations
  - Support: Support, Escalations
  - Content: Knowledge
  - Insights: Analytics, Operations
  - Admin: Settings
- **Top bar:** Search, notifications, language switcher, user
- **Content area:** Main content with consistent padding
- **Mobile:** Collapsible sidebar overlay, hamburger menu

## 2. Modern Dashboard

**File:** `console/templates/console/dashboard.html`

- **KPI cards:** New leads, Active conversations, Support cases, Escalations (with links)
- **Secondary metrics:** Hot/warm/cold leads, AI responses
- **Charts (Chart.js):**
  - Conversation sources (doughnut)
  - Lead temperature (bar)
- **Quick actions:** Link row for fast navigation

## 3. Conversation Workspace

**Files:** `console/conversations.html`, `console/conversation_detail.html`

- **Left panel:** Conversation list with customer name, channel, message count
- **Center:** Chat thread with message bubbles, feedback actions
- **Right panel:** Customer context (lead score, intent, budget, escalations, support cases)
- **Empty state:** "Select a conversation" with CTA to try chat

## 4. Customer Profile

**File:** `console/customer_detail.html`

- **Left column:** Profile, Identity, Lead scores
- **Right column:** Conversation history, Support cases, Recommendations, Timeline
- Clean card-based layout

## 5. Support Workspace

**File:** `console/support_cases.html`

- **Kanban columns:** Open, In Progress, Escalated, Resolved
- **Cards:** ID, severity, summary, customer name
- **Status badges:** Color-coded by status

## 6. Knowledge Management

**File:** `console/knowledge.html`

- **Document cards:** Title, type, status, version, verification
- **Processing status:** Indexed / processing badge
- **Actions:** View link

## 7. Analytics

**File:** `console/analytics.html`

- **Chart.js visualizations:**
  - Leads by source (bar)
  - Top intents (doughnut)
  - Support categories (horizontal bar)
  - Escalation reasons (doughnut)
- Period selector (7/30/90 days)

## 8. Empty States

**File:** `console/includes/empty_state.html`

- Icon variants: default, chat, users, support, documents
- Title, explanation, call-to-action button
- Updated copy: "Start by connecting a channel or sending a test message"

## 9. Global Search

**Files:** `console/views.py` (search view), `console/search.html`

- **Top bar:** Search input → `/console/search/?q=...`
- **Results:** Customers, Conversations, Projects, Support cases
- **Search logic:** Name, email, external_id for customers; ID or customer name for conversations; name/name_ar/location for projects; summary/category for support

## 10. Notifications

- **Top bar:** Bell icon linking to Escalations, red dot when open escalations exist

## 11. Visual Hierarchy

- **Spacing:** Tailwind `p-4`, `p-6`, `gap-4`, `gap-6`
- **Typography:** Font weights (medium, semibold, bold), `text-slate-500` for secondary
- **Cards:** `rounded-xl`, `border border-slate-200`, `hover:shadow-md`
- **Hover states:** `hover:bg-slate-50`, `hover:border-teal-200`

## 12. Responsiveness

- **Sidebar:** Hidden on mobile, overlay when toggled
- **Grids:** `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`
- **Support Kanban:** `overflow-x-auto` for horizontal scroll on small screens

## 13. Loading States

- **Skeleton CSS:** `.skeleton` class in base with shimmer animation
- **Skeleton component:** `console/includes/skeleton.html` – variants: `card`, `kpi`, `list-item`, `list-5`, `chart`
- Use with HTMX or fetch: return skeleton HTML as placeholder, then swap with real content
- Charts render after DOM ready

## Files Modified

| File | Changes |
|------|---------|
| `console/base.html` | Sidebar, top bar, layout |
| `console/dashboard.html` | KPI cards, Chart.js |
| `console/conversations.html` | 3-panel workspace list |
| `console/conversation_detail.html` | 3-panel with customer context |
| `console/customer_detail.html` | Structured profile sections |
| `console/support_cases.html` | Kanban columns |
| `console/knowledge.html` | Card layout |
| `console/analytics.html` | Chart.js charts |
| `console/includes/empty_state.html` | Icon variants, improved CTA |
| `console/search.html` | Search results page (customers, conversations, projects, support) |
| `console/knowledge_doc_detail.html` | SaaS-style document detail with grid layout, retrieval test panel |
| `console/includes/skeleton.html` | Reusable skeleton loaders (card, kpi, list, chart) |
| `console/views.py` | Search view, support columns, conversation list in detail |
| `console/urls.py` | Search route |
| `console/context_processors.py` | Stats for top bar |
| `config/settings.py` | Context processor |

## Verification Steps

1. **Dashboard:** `/console/` – KPI cards, charts, quick actions
2. **Conversations:** `/console/conversations/` – List left, select conversation → detail
3. **Conversation detail:** 3-panel layout, customer context right
4. **Customer:** `/console/customers/<id>/` – Profile, sections
5. **Support:** `/console/support/` – Kanban columns
6. **Knowledge:** `/console/knowledge/` – Document cards
7. **Analytics:** `/console/analytics/` – Charts
8. **Search:** Top bar → type and submit → results (customers, conversations, projects, support)
9. **Knowledge doc:** `/console/knowledge/<id>/` – metadata, chunks, retrieval test panel
10. **Mobile:** Resize to tablet width – sidebar collapses, hamburger works
