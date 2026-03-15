# Channel Abstraction Layer – Design

Clean inbound channel abstraction for website chat and WhatsApp readiness. Single normalized schema feeds canonical orchestration.

---

## 1. Channel Abstraction Design

### Normalized Message Schema (NormalizedInboundMessage)

| Field | Type | Purpose |
|-------|------|---------|
| content | str | Message text |
| source_channel | str | web, whatsapp, demo |
| external_id | str | Channel-specific user id |
| phone | str | Phone number |
| email | str | Email |
| name | str | Display name |
| timestamp | datetime | Message timestamp |
| campaign | str | UTM campaign, etc. |
| source | str | UTM source, lead source |
| conversation_id | int? | Existing conversation |
| customer_id | int? | Resolved customer |
| metadata | dict | Channel-specific extras |

### Adapter Interface

```python
class BaseChannelAdapter(ABC):
    channel_name: str
    def normalize(raw_payload: dict) -> NormalizedInboundMessage
    def validate(raw_payload: dict) -> tuple[bool, str]
```

### Implementations

| Adapter | Channel | Payload Shape |
|---------|---------|---------------|
| WebChannelAdapter | web, demo | content, channel, external_id, phone, email, name, campaign, source, conversation_id, customer_id |
| WhatsAppChannelAdapter | whatsapp | Direct: content, phone, external_id. Webhook: entry→changes→value→messages→text.body |

---

## 2. Design Choices

1. **Single schema** – All channels produce NormalizedInboundMessage; orchestration receives one format.
2. **Adapter per channel** – Web and WhatsApp as separate adapters; add Instagram, API, etc. later.
3. **Demo fits** – Web payload with channel=web or channel=demo uses WebChannelAdapter.
4. **Orchestration unchanged** – to_orchestration_params() maps to existing run_orchestration kwargs.
5. **WhatsApp placeholder** – Supports direct shape (testing) and webhook shape (ready for Meta API).
6. **No DB models** – Stateless; no migrations.

---

## 3. Files Changed

| File | Changes |
|------|---------|
| `channels/` (new app) | schema.py, adapters/base.py, web.py, whatsapp.py, service.py, views.py, urls.py, tests.py |
| `config/settings.py` | Added "channels" to INSTALLED_APPS |
| `core/api_urls.py` | path("channels/", include("channels.urls")) |
| `orchestration/views.py` | Uses process_inbound_message for orchestration API |

---

## 4. Migrations

None – channel layer is stateless.

---

## 5. Tests Added

| Test | Purpose |
|------|---------|
| test_normalized_message_schema | Schema fields and to_orchestration_params |
| test_web_adapter_normalize | Web payload → NormalizedInboundMessage |
| test_web_adapter_requires_content | ValueError when content empty |
| test_whatsapp_adapter_direct_shape | Direct payload with content, phone |
| test_whatsapp_adapter_webhook_shape | Webhook entry→changes→messages parsing |
| test_normalize_inbound_web | normalize_inbound returns schema |
| test_process_inbound_runs_orchestration | Full flow: normalize → orchestration |

---

## 6. Verification Steps

1. `pytest channels/tests.py -v`
2. `pytest orchestration/tests.py -v`
3. POST to `/api/orchestration/run/` with content, channel=web – same behavior as before
4. POST with channel=whatsapp, content, phone – processes via WhatsApp adapter
5. GET `/api/channels/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=...&hub.challenge=OK` – returns challenge for Meta verification

---

## 7. Risks & Follow-up

| Risk | Mitigation / Follow-up |
|------|------------------------|
| Demo flow bypasses channels | orchestration.service.run_canonical_pipeline still calls run_orchestration directly; can later route through channels |
| WhatsApp webhook security | Add verify_token check; validate Meta signature when live |
| Non-text WhatsApp messages | Current adapter handles text only; add image/button handlers when needed |
| Campaign/source not persisted | Metadata passed in msg; can store in LeadProfile or CRM when desired |
