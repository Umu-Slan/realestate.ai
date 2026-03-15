# Arabic-First i18n Implementation

Production-grade Arabic-first interface with full English support for the Real Estate AI console.

## 1. Django i18n Configuration

**File:** `config/settings.py`

- `USE_I18N = True` – Internationalization enabled
- `USE_L10N = True` – Localization for dates/numbers
- `LANGUAGE_CODE = env("LANGUAGE_CODE", default="ar")` – Arabic as default
- `LANGUAGES = [("ar", "العربية"), ("en", "English")]`
- `LOCALE_PATHS = [BASE_DIR / "locale"]`
- `django.template.context_processors.i18n` – Added to `TEMPLATES`
- `LocaleMiddleware` – Already in `MIDDLEWARE` (after `SessionMiddleware`)

## 2. Translation Infrastructure

- **Translation tags:** All UI strings wrapped with `{% trans %}` and `{% blocktrans %}`
- **Arabic translations:** `locale/ar/LC_MESSAGES/django.po` (Arabic strings)
- **English catalog:** `locale/en/LC_MESSAGES/django.po` (fallback)
- **Compiled:** `locale/ar/LC_MESSAGES/django.mo` (compiled with Babel)

### Generating/Updating .po Files

Django’s `makemessages` needs GNU gettext (`xgettext`, `msgfmt`). On Windows:

1. Install gettext from [mlocati.github.io/gettext-iconv-windows](https://mlocati.github.io/articles/gettext-iconv-windows.html)
2. Add gettext `bin` directory to `PATH`
3. Run: `python manage.py makemessages -l ar -l en --ignore=.venv`

Alternatively, use Babel for compiling only (`.po` → `.mo`):

```bash
pip install babel
pybabel compile -d locale -D django -l ar
```

## 3. Translated UI Areas

| Section | Templates Updated |
|---------|-------------------|
| Base | `console/base.html` |
| Dashboard | `console/dashboard.html` |
| Conversations | `console/conversations.html`, `conversation_detail.html` |
| Customers | `console/customers.html`, `customer_detail.html` |
| Support | `console/support_cases.html`, `support_case_detail.html` |
| Escalations | `console/escalations.html` |
| Knowledge | `console/knowledge.html` |
| Analytics | `console/analytics.html` |
| Operations | `console/operations.html` |
| Onboarding | `onboarding/dashboard.html` |
| Auth | `accounts/login.html` |
| Empty states | `console/includes/empty_state.html` |

## 4. Arabic UX Text Replacements

| English | Arabic |
|---------|--------|
| No messages yet | لا توجد رسائل بعد |
| No data for this period | لا توجد بيانات لهذه الفترة |
| Add data or run a flow to get started | ابدأ بإضافة بيانات أو تشغيل تدفق |
| No conversations | لا توجد محادثات |
| No customers | لا يوجد عملاء |
| (and 150+ other strings) | See `locale/ar/LC_MESSAGES/django.po` |

## 5. RTL Support

- `dir="rtl"` on `<html>` when `LANGUAGE_BIDI` (Arabic)
- Nav uses `flex-row-reverse` in RTL
- `mr-auto` / `ml-auto` swapped for language switcher
- RTL overrides in base styles:
  - Table headers: `text-align: right`
  - `.ml-2`, `.ml-8`, `.mr-8` margins mirrored
  - `.border-l-4` → right border in RTL

## 6. Arabic Typography

- Font stack: IBM Plex Sans Arabic, Noto Sans Arabic, Tajawal
- Loaded via Google Fonts in `base.html`

## 7. Arabic Chat Responses

**Files:** `engines/templates.py`, `engines/sales_engine.py`, `engines/support_engine.py`

- Sales prompt: explicit instruction for natural Egyptian Arabic (لهجة مصرية راقية), phrases مثل "أهلاً وسهلاً", "بكل تأكيد", "حاضر"
- Support prompt: empathetic Arabic مثل "فهمت"، "أسف لسماع ذلك"، "حاضر، سنتابع"
- `detect_response_language()` used for objection/fallback responses
- All openings/closings in TEMPLATES already have `opening_ar`, `closing_ar`

## 8. Date and Number Formatting

- `USE_L10N = True` – locale-aware formats when using Django format names
- For locale-aware dates, prefer `{{ value|date }}` (no format) or `{{ value|date:"SHORT_DATE_FORMAT" }}`
- Current templates use `date:"M d, Y H:i"` for consistency; can be switched to locale formats if desired

## 9. Language Switcher

- Position: top nav, next to Chat/Tools
- Form: POST to `/i18n/setlang/` (Django `set_language`)
- Buttons: العربية | English – highlights active language
- URL: `config/urls.py` – `path("i18n/setlang/", set_language, name="set_language")`

## 10. Verification Steps

1. **Dashboard:** Visit `/console/` – Arabic nav, dashboard labels, RTL layout
2. **Conversations:** `/console/conversations/` – table headers, empty state
3. **Customer profile:** `/console/customers/<id>/` – layout and labels
4. **Support cases:** `/console/support_cases/` – table and empty state
5. **Analytics:** `/console/analytics/` – period selector, “No data” messages
6. **Language switch:** Click “English” – UI switches to LTR and English
7. **Login:** `/accounts/login/` – form labels and messages in active language

## Files Changed Summary

| Category | Files |
|----------|-------|
| Settings | `config/settings.py` |
| URLs | `config/urls.py` |
| Base layout | `console/templates/console/base.html` |
| Console templates | `dashboard`, `conversations`, `customers`, `support_cases`, `escalations`, `knowledge`, `analytics`, `operations`, `conversation_detail`, `empty_state` |
| Onboarding | `onboarding/templates/onboarding/dashboard.html` |
| Auth | `accounts/templates/accounts/login.html` |
| Engines | `engines/templates.py` |
| Locales | `locale/ar/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po`, `locale/ar/LC_MESSAGES/django.mo` |
