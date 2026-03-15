# Internal Operator Console

## Overview

Usable internal web interface for real estate operators to inspect and manage the AI system.

## Routes

| Path | Page |
|------|------|
| `/console/` | Dashboard |
| `/console/conversations/` | Conversation inbox |
| `/console/conversations/<id>/` | Conversation detail |
| `/console/customers/` | Customer list |
| `/console/customers/<id>/` | Customer profile |
| `/console/support/` | Support cases queue |
| `/console/escalations/` | Escalations queue |
| `/console/recommendations/` | Recommendations panel |
| `/console/knowledge/` | Knowledge documents |
| `/console/knowledge/<id>/` | Document detail (chunks) |
| `/console/audit/` | Audit log explorer |
| `/console/corrections/` | Human correction interface |
| `/console/demo/` | Demo scenarios |

## UI Structure

- **Nav bar**: Links to all main sections
- **Dashboard**: Stats cards, demo walkthrough steps
- **Conversation detail**: Messages, intent, customer type, score, qualification, reason codes, action logs, feedback (Good / Correct)
- **Customer profile**: Identity, timeline (messages, CRM notes, scores, support, escalations, recommendations)
- **Knowledge**: Document metadata, verification status, chunk previews
- **Corrections**: Form to submit human corrections; list of recent corrections

## Conversation View

- Messages with role and timestamp
- Orchestration snapshot (when available): intent, customer type, score, temperature
- Latest LeadScore with reason codes
- Qualification (budget, location, property type)
- Action logs
- Feedback buttons: **Good** (mark response OK), **Submit correction** (corrected text + reason)

## Customer Profile

- Identity (external_id, phone, email, name)
- Timeline: messages, CRM notes, lead scores, support cases, escalations, recommendations
- CRM history
- Past lead temperatures

## Human Correction

1. **Mark good**: Click "Good" on any assistant message (creates ResponseFeedback)
2. **Submit correction**: Use the Corrections page form or the inline form on conversation detail
   - Subject type: `message`
   - Subject ID: message ID
   - Field: `response`
   - Original value, corrected value, reason

## Demo Walkthrough Steps

1. **Load demo data**: `python manage.py load_demo_data`
2. **Start server**: `python manage.py runserver`
3. Open **Dashboard** at `/console/` for overview and stats
4. **Conversations** → click one → see messages, intent, score, qualification, next best action, sources, action logs, feedback (Good / Submit correction)
5. **Customers** → click one → see identity, timeline (messages, CRM, scores, support, escalations, recommendations), past lead temperatures
6. **Support Cases** and **Escalations** queues
7. **Recommendations** panel
8. **Knowledge** → open document → metadata, chunks, retrieval test query
9. **Audit Log** for system actions
10. **Corrections** → submit human corrections, view recent corrections
11. **Demo Scenarios** → links to engines demo and APIs

## Styling

- Tailwind CSS via CDN
- Clean, professional internal styling
- Responsive layout
