# v0 Limitations and Future Roadmap

An honest, professional summary of what v0 does not yet do and where we plan to go.

---

## Known Limitations in v0

### Channels & Integration

- **No live WhatsApp/Instagram**: Conversations are via API and Operator Console only. No native adapters for WhatsApp Business API or Instagram DMs.
- **No CRM vendor sync**: CRM import is CSV/Excel file upload. No direct sync with Salesforce, HubSpot, Zoho, or other CRM systems.
- **No voice layer**: No IVR, no speech-to-text, no voice responses. Text-only for now.

### Knowledge & Retrieval

- **Vector search**: pgvector is used; retrieval can fail if embeddings are not populated or if the pgvector extension has compatibility issues. We document workarounds.
- **Stale content**: Documents can become stale. Verification status and validity windows exist but require manual or scheduled upkeep.
- **Limited document types**: PDF, TXT, CSV ingestion supported. Excel and complex layouts may need pre-processing.

### Intelligence & Scoring

- **Intent coverage**: 15+ intent categories; edge cases (sarcasm, mixed intents, very short messages) may misclassify.
- **Qualification extraction**: Budget, location, property type extracted. Family size, financing details are partial.
- **Scoring**: Deterministic rules. No ML-based scoring yet; no historical conversion signals.
- **Arabic vs English**: Optimized for Egyptian Arabic and mixed Ar/En. Pure English or other dialects may perform less well.

### Safety & Compliance

- **Guardrails are heuristic**: Pattern-based checks for unverified prices, legal advice, delivery promises. Sophisticated circumvention is possible.
- **No PII redaction in logs**: Audit logs may contain customer content. Review before external sharing.
- **No multi-tenant isolation**: Single-tenant for v0. No customer/company scoping.

### Operations

- **Console auth**: Operator Console does not enforce login by default for local demo. Production deployment should add authentication.
- **Celery optional**: Async tasks (e.g. batch embedding) may not run if Redis/Celery is not configured.
- **No SLA monitoring**: No built-in latency or throughput dashboards.

---

## Future Roadmap (Short)

### Phase 1: Channels

- **WhatsApp Business API adapter**: Receive and send messages via WhatsApp.
- **Instagram DM adapter**: Same for Instagram.
- **Unified inbox**: Single view across web, WhatsApp, Instagram.

### Phase 2: CRM & Data

- **CRM vendor integration**: Bi-directional sync with major CRMs (Salesforce, HubSpot).
- **Structured pricing API**: Pull prices from internal systems; avoid manual Project updates.
- **CRM-driven triggers**: Inbound events from CRM (e.g. lead status change) to trigger AI actions.

### Phase 3: Geography & Localization

- **Multi-country**: GCC, North Africa with locale-specific projects and pricing.
- **RTL and locale**: Full RTL UX, locale-specific date/currency formats.

### Phase 4: Voice & Multimodal

- **Voice layer**: IVR integration, speech-to-text, TTS for phone.
- **Image input**: Property photos for classification or matching.

### Phase 5: Analytics & Intelligence

- **Conversion attribution**: Link scored leads to actual sales.
- **ML-based scoring**: Train on historical conversion data.
- **Advanced analytics dashboard**: Funnels, cohort analysis, A/B tests.

---

## What v0 Is Designed For

- **Internal pilot**: Prove the pipeline, guardrails, and operator visibility.
- **Stakeholder demos**: Show qualification, scoring, routing, and audit.
- **Evaluation baseline**: 85 scenarios to track intent, temperature, routing accuracy.
- **Foundation for scale**: Architecture supports adding channels, CRM, and ML without rewrites.

It is not designed to replace human agents today. It is designed to augment them with consistent qualification, routing, and safe first-response behavior.
