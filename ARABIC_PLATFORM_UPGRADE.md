# Arabic-First AI Platform Upgrade

Production-grade Arabic-first interface with intelligent conversational behavior for Egypt and Arabic-speaking markets.

---

## PART 1 — Arabic UX Hardening

### 1. UI String Audit

**Templates updated with `{% trans %}` / `{% blocktrans %}`:**

| Area | Files |
|------|-------|
| Conversation detail | `conversation_detail.html` – Customer & Routing, Intent, Score, Stage, Qualification, Budget, Location, Property type, Escalations, Support Cases, Action Logs, feedback (Marked good, Corrected, Good, Submit correction, Issue type, Reason) |
| Recommendations | `recommendations.html` – full panel, table headers, empty state |
| Onboarding | `onboarding/dashboard.html` – Documents, Structured Data, CRM Export, Reindex, Recent Batches, table headers, buttons |
| Base | Already covered in prior i18n work |

### 2. Arabic UX Wording

| English | Arabic |
|---------|--------|
| No conversations | لا توجد محادثات بعد |
| No support cases | لا توجد طلبات دعم |
| Add data or run a flow to get started | ابدأ بإضافة بيانات أو تشغيل أحد التدفقات |
| No recommendations | لا توجد توصيات حالياً |
| Processing document | جارٍ معالجة الملف... |
| Operation successful | تم تنفيذ العملية بنجاح |

### 3. RTL Behavior

- `dir="rtl"` on `<html>` when Arabic is active
- **Message bubbles:** `.msg-user` / `.msg-assistant` with RTL-aware margins and borders
- Table headers: `text-align: right` in RTL
- Nav: `flex-row-reverse`, `mr-auto`/`ml-auto` swapped for language switcher

### 4. Arabic Typography

- Font stack: IBM Plex Sans Arabic, Noto Sans Arabic, Tajawal
- `line-height: 1.75` for Arabic/RTL (vs 1.6 for LTR)

### 5. Arabic-Friendly Numbers and Prices

- Format: `3,000,000 جنيه` (e.g. in `response_builder.py`)
- Recommendation rationale shows: "نطاق أسعار تقريبي: X–Y جنيه"
- Typo fix: "يُرجع التأكد" → "يرجى التأكد"

### 6. System Messages

- `Processing document` → جارٍ معالجة الملف...
- `Operation successful` → تم تنفيذ العملية بنجاح

---

## PART 2 — Arabic Intelligence Upgrade

### 7. Conversation Prompts

**File:** `engines/templates.py`

Rewritten system prompts for:

- Natural Egyptian Arabic (أهلاً وسهلاً، بكل تأكيد، يسعدني مساعدتك، تحت أمرك)
- Adaptive tone and varied phrasing
- Context awareness
- Polite but persuasive sales tone

### 8. Sales Conversation Intelligence

- Ask clarifying questions for ambiguous queries
- Adapt to user budget
- Suggest relevant projects with reasoning
- Guide conversation without rigid scripts

### 9. Example Behaviors

**User:** عايز شقة في الشيخ زايد  
**AI:** تمام، هل تفضل شقة جاهزة للاستلام أم مشروع قيد الإنشاء؟ وكمان لو تحب توضح الميزانية التقريبية أقدر أرشح لك خيارات مناسبة.

**User:** معايا حوالي 3 مليون  
**AI:** ميزانية 3 مليون تفتح لك عدة خيارات جيدة. هل تفضل الشيخ زايد أم القاهرة الجديدة؟

### 10. Intelligent Follow-Up

- If user message is incomplete, ask targeted questions
- Example: هل تبحث عن سكن شخصي أم للاستثمار؟

### 11. Support Empathy

**User:** أنا متضايق من التأخير  
**AI:** أتفهم انزعاجك من التأخير، وسأحاول مساعدتك بأسرع وقت. هل يمكن توضيح رقم الحجز أو المشروع المرتبط بالطلب؟

### 12. Anti-Repetition

- Prompts instruct to vary phrasing
- Avoid repeating identical sentence structures

### 13. Context Memory

- Explicit rule: never re-ask for budget, location, or project if already stated
- `_build_sales_context` adds: "CONTEXT RULE: The conversation history contains prior messages. Never re-ask for budget, location, or project preference if the customer has already stated it."

### 14. Recommendation Explanation

- Response builder includes qualification summary in intro when available
- Prompts instruct: "رشحت لك هذا المشروع لأنه يقع في [المنطقة] وسعره ضمن الميزانية التي ذكرتها."

### 15. Politeness Layer

- أهلاً وسهلاً، بكل تأكيد، يسعدني مساعدتك، تحت أمرك
- Vary usage; do not repeat in every message

---

## Files Modified

| Category | Files |
|----------|-------|
| Templates | `console/conversation_detail.html`, `console/recommendations.html`, `console/base.html`, `onboarding/dashboard.html` |
| Engines | `engines/templates.py`, `engines/sales_engine.py`, `engines/response_builder.py` |
| Locales | `locale/ar/LC_MESSAGES/django.po`, `locale/ar/LC_MESSAGES/django.mo` (compiled) |

---

## Verification Steps

1. **Arabic UI:**
   - `/console/dashboard` – RTL, Arabic labels
   - `/console/conversations` – table, empty state
   - `/console/customers` – layout
   - `/console/support_cases` – table, empty state "لا توجد طلبات دعم"
   - `/console/analytics` – period selector, "No data" messages

2. **Arabic chat scenarios:**
   - "عايز شقة في الشيخ زايد" → clarifying questions
   - "معايا 3 مليون" → budget acknowledgment + location question
   - "رشحلي مشروع للاستثمار" → recommendations with reasoning
   - "أنا متضايق من التأخير" → empathetic support response

3. **Language switch:** English → LTR layout restored
