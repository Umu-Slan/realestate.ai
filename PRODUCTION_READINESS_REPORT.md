# Production Readiness Audit Report

**Date:** 2025-03-09  
**Scope:** Deployment readiness evaluation. No new features.

---

## 1. Production Readiness Score: **72/100**

| Category | Score | Notes |
|----------|-------|-------|
| Environment configuration | 7/10 | Documented; production overrides required |
| Docker setup | 8/10 | Infra only (Postgres+Redis); no app container |
| PostgreSQL reliability | 9/10 | Health check, wait_for_db, pgvector init |
| Redis reliability | 8/10 | Optional; health check; Celery configured |
| Migrations state | 9/10 | Consistent; pgvector in knowledge |
| Secret management | 5/10 | Env-based; weak default; no validation |
| Debug flags | 6/10 | Default True; must override in prod |
| Logging configuration | 5/10 | Django default only; no file/JSON |
| API error responses | 8/10 | Consistent; 500 generic; JSON-safe |
| Console authentication | 4/10 | No login required; open by design |
| CSRF protection | 7/10 | Middleware on; API exempt (intentional) |
| Rate limiting | 3/10 | None configured |
| Resource usage | 7/10 | No limits; connection pooling optional |
| Model loading | 8/10 | Standard Django; no lazy issues |
| Startup reliability | 8/10 | wait_for_db; health endpoints |

---

## 2. Issues Detected

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | SECRET_KEY defaults to "dev-secret-key-change-in-production" | High | `config/settings.py` |
| 2 | DEBUG defaults to True | High | `config/settings.py` |
| 3 | No env validation at startup | Medium | - |
| 4 | Console has no authentication | Medium | `console/views.py` |
| 5 | No rate limiting on API | Medium | - |
| 6 | No LOGGING config (file/rotation) | Low | `config/settings.py` |
| 7 | CORS_ALLOW_ALL_ORIGINS when DEBUG | Low | Tied to DEBUG |
| 8 | No application Dockerfile | Low | App runs on host |
| 9 | Demo data mixed with production tables | Low | Demo uses same DB |

---

## 3. Fixes Applied

| # | Fix | File |
|---|-----|------|
| 1 | Add Django system check for SECRET_KEY when DEBUG=False | `core/checks.py`, `core/apps.py` |
| 2 | Document production variables in .env.example | `.env.example` |

---

## 4. Files Changed

| File | Changes |
|------|---------|
| `core/checks.py` | New: production SECRET_KEY check |
| `core/apps.py` | Import checks in ready() |
| `.env.example` | Production override note |

---

## 5. Recommended Deployment Configuration

### 5.1 Required Environment Variables (Production)

```env
# CRITICAL - Must override
SECRET_KEY=<generate-with-openssl-rand-hex-32>
DEBUG=false
ALLOWED_HOSTS=your-domain.com,api.your-domain.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/realestate_ai

# Redis (if using Celery)
CELERY_BROKER_URL=redis://host:6379/1
REDIS_URL=redis://host:6379/0

# AI (if not demo mode)
DEMO_MODE=false
OPENAI_API_KEY=sk-...
```

### 5.2 Startup Sequence

```bash
# 1. Start infrastructure
docker compose up -d   # or external Postgres+Redis

# 2. Wait for database
python manage.py wait_for_db

# 3. Validate
python manage.py check
python manage.py check_local_setup

# 4. Migrate
python manage.py migrate

# 5. Collect static
python manage.py collectstatic --noinput

# 6. Run server (gunicorn/uwsgi in production)
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### 5.3 Server Restart Safety

- **Migrations:** Run `migrate --check` in CI; run `migrate` before deploy
- **No migration conflicts** with multiple workers (Django handles)
- **Connection pooling:** Consider `CONN_MAX_AGE=60` in DATABASES when not using PgBouncer

### 5.4 Demo Data vs Production

- Demo data uses same tables (Customer, Conversation, etc.) with `external_id` prefixed by `demo:`
- `load_demo_data`, `run_demo` are management commands
- **Production:** Do not run `run_demo` or `load_demo_data`; use fresh DB or seed with real data
- Console `/console/demo/` pages show eval scenarios; safe if demo app not loaded

### 5.5 Security Hardening Recommendations

| Item | Action |
|------|--------|
| Console auth | Add `LOGIN_URL` and `@login_required` to console views, or restrict by IP |
| Rate limiting | Add `DEFAULT_THROTTLE_CLASSES` to REST_FRAMEWORK for API |
| HTTPS | Use reverse proxy (nginx, Caddy) with TLS |
| Static files | Serve via CDN or nginx; avoid Django in prod |

### 5.6 Verification Commands

```bash
python manage.py check              # Includes SECRET_KEY check when DEBUG=False
python manage.py check_local_setup  # DB, pgvector
python manage.py migrate --check    # Migration consistency
curl http://localhost:8000/health/   # Aggregated health
```
