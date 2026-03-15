# Production Deployment Guide

Real Estate AI System – deployment setup for production use.

---

## 1. Overview

| Component | Role |
|-----------|------|
| **App** | Django + Gunicorn, serves API and console |
| **PostgreSQL** | Primary database with pgvector |
| **Redis** | Celery broker (optional for minimal deploy) |
| **Static files** | Served by WhiteNoise in production |
| **Media files** | Operator uploads; persisted via volume; served by reverse proxy |

---

## 2. Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret (50+ chars) | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `your-domain.com,www.your-domain.com` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@host:5432/dbname` |

### Production Overrides

| Variable | Default | Production |
|----------|---------|------------|
| `DEBUG` | `true` | `false` |
| `DJANGO_ENV` | `development` | `production` |
| `DJANGO_SETTINGS_MODULE` | `config.settings` | `config.settings_production` |

### Optional (Production Hardening)

| Variable | Description | Example |
|----------|-------------|---------|
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins for HTTPS forms/AJAX | `https://your-domain.com,https://www.your-domain.com` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins | `https://your-domain.com` |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | Max upload size (bytes); default 10MB | `10485760` |
| `MEDIA_ROOT` | Override media path (default: `BASE_DIR/media`) | `/app/media` |
| `CELERY_BROKER_URL` | Redis for Celery (optional) | `redis://redis:6379/1` |
| `REDIS_URL` | Celery result backend | `redis://redis:6379/0` |
| `OPENAI_API_KEY` | LLM provider key | `sk-...` |
| `DEMO_MODE` | `true` = mock LLM, `false` = live | `false` |

See `.env.production.example` for a full template.

---

## 3. Docker Deployment

### Prerequisites

- Docker and Docker Compose
- `.env` file with production values

### Build and Run

```bash
# 1. Copy and edit env
cp .env.production.example .env
# Edit .env: SECRET_KEY, ALLOWED_HOSTS, POSTGRES_PASSWORD

# 2. Production first-run checklist (see §3.1)

# 3. Build
docker compose -f docker-compose.production.yml build

# 4. Run (migrate + collectstatic run automatically)
docker compose -f docker-compose.production.yml up -d

# 5. Verify
curl http://localhost:8000/health/ready/
curl http://localhost:8000/health/
```

### 3.1 Environment Variable Checklist

Before first run, ensure:

- [ ] `SECRET_KEY` – strong random string (50+ chars)
- [ ] `ALLOWED_HOSTS` – includes your public domain(s) and `localhost` for local testing
- [ ] `POSTGRES_PASSWORD` – strong password for DB
- [ ] `CSRF_TRUSTED_ORIGINS` – if using HTTPS, add `https://your-domain.com` (and www if used)
- [ ] `CORS_ALLOWED_ORIGINS` – if the frontend or API consumers use a different origin
- [ ] `OPENAI_API_KEY` – if `DEMO_MODE=false`

### 3.2 Startup Order (Docker Compose)

Containers start in dependency order:

1. **PostgreSQL** and **Redis** – start first; healthchecks must pass
2. **App** – waits for `postgres:healthy` and `redis:healthy`, then:
   - `wait_for_db` (redundant with depends_on, but safe)
   - `migrate --noinput`
   - `collectstatic --noinput`
   - Gunicorn

**Celery worker/beat**: Not required. No background tasks use Celery today. Redis is used for optional Celery broker; app runs fine without a worker.

### 3.3 In-Container Startup Sequence

Inside the app container:

1. `wait_for_db` – polls PostgreSQL until ready
2. `migrate --noinput`
3. `collectstatic --noinput`
4. Gunicorn

---

## 4. Reverse Proxy & HTTPS

The compose stack exposes Gunicorn on port 8000. For production, put a reverse proxy in front for HTTPS and static/media serving.

### 4.1 Recommended: Caddy or Nginx

**Caddy** (automatic HTTPS with Let's Encrypt):

```caddyfile
your-domain.com {
    reverse_proxy localhost:8000
}
```

**Nginx** (manual certs or use Certbot):

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve media files directly (faster than proxying through Django)
    location /media/ {
        alias /path/to/media/;  # Mount from app container or shared volume
    }
}
```

### 4.2 Django Settings When Behind HTTPS

Set in `.env`:

```
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

---

## 5. Media Files

| Setting | Value | Notes |
|---------|-------|-------|
| `MEDIA_ROOT` | `BASE_DIR / "media"` (default) | In Docker: `/app/media` |
| `MEDIA_URL` | `media/` | URLs like `/media/onboarding/uploads/...` |

### 5.1 Persistence in Docker

The app service mounts a named volume at `/app/media`:

- **Volume**: `media_prod_data`
- **Path**: `/app/media` inside container
- Operator-uploaded docs, CSV, and knowledge files are stored here and persist across container restarts.

### 5.2 Serving Media in Production

Django does **not** serve media when `DEBUG=False`. Options:

1. **Reverse proxy** (recommended): Nginx/Caddy serves `/media/` from the filesystem.
   - **Nginx on host**: Use a bind mount in compose, e.g. `./media_data:/app/media` instead of `media_prod_data`, so the host path is available to nginx.
   - **Nginx in Docker**: Add nginx to the compose stack and mount the same `media_prod_data` volume at `/app/media`.
2. **Object storage**: For multi-node deployments, use `django-storages` (S3, etc.) and set `MEDIA_ROOT` / `MEDIA_URL` accordingly.

### 5.3 Upload Safety

- **Allowed extensions**: `.pdf`, `.csv`, `.xlsx`, `.xls`, `.txt`, `.md` (onboarding document batch)
- **Path sanitization**: Filenames sanitized to prevent path traversal
- **Size limit**: `FILE_UPLOAD_MAX_MEMORY_SIZE` (default 10MB)

---

## 6. Celery Topology

| Component | Required? | Notes |
|-----------|-----------|-------|
| Redis | Optional | Used as Celery broker; health checks tolerate absence |
| Celery worker | **No** | No `@shared_task` or `apply_async` in codebase |
| Celery beat | **No** | No periodic tasks defined |

Redis can be omitted for minimal deploys; the app runs without it. If you add Celery tasks later, add a worker service and keep Redis.

---

## 7. Allowed Hosts & CORS Examples

### ALLOWED_HOSTS

```
# Single domain
ALLOWED_HOSTS=your-domain.com

# Domain + www + localhost for tests
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,localhost

# With port (dev)
ALLOWED_HOSTS=localhost,127.0.0.1,[::1]
```

### CSRF_TRUSTED_ORIGINS (HTTPS)

```
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### CORS (if API consumed from another origin)

```
CORS_ALLOWED_ORIGINS=https://app.your-domain.com,https://admin.your-domain.com
```

---

## 8. Manual / Non-Docker Deployment

### 8.1 App Server (Gunicorn)

```bash
# Set production env
export DJANGO_ENV=production
export DJANGO_SETTINGS_MODULE=config.settings_production
export SECRET_KEY="your-secret"
export ALLOWED_HOSTS="your-domain.com"

# Wait for DB (if needed)
python manage.py wait_for_db

# Migrate
python manage.py migrate --noinput

# Static files
python manage.py collectstatic --noinput

# Run
gunicorn config.wsgi:application -c gunicorn.conf.py
```

### 8.2 Database (PostgreSQL + pgvector)

- PostgreSQL 14+ with pgvector extension
- Run migrations: `python manage.py migrate`
- Init pgvector: `CREATE EXTENSION IF NOT EXISTS vector;` (or use Docker init script)

### 8.3 Redis (Optional)

- Used by Celery. If not running Celery, app works without Redis.
- Health check `/health/redis/` returns fail when Redis unavailable; `/health/` still OK if DB+vector pass.

---

## 9. Health Checks

| Endpoint | Purpose |
|----------|---------|
| `/health/` | Aggregated: DB, Redis, Vector, Model |
| `/health/ready/` | Readiness: DB only (for load balancers) |
| `/health/db/` | Database connectivity |
| `/health/redis/` | Redis connectivity |
| `/health/vector/` | pgvector extension |
| `/health/model/` | LLM config presence |

Kubernetes / load balancers should use `/health/ready/` for readiness.

---

## 10. Validation

Before deploying:

```bash
export DJANGO_SETTINGS_MODULE=config.settings_production
python manage.py validate_deployment
```

Options:

- `--skip-db` – skip database check
- `--skip-migrations` – skip migration check
- `--skip-static` – skip static collect check
- `--strict` – fail on warnings

---

## 11. Static Files

- **Development**: `runserver` serves static automatically.
- **Production**: WhiteNoise serves files from `STATIC_ROOT` after `collectstatic`.
- Run `python manage.py collectstatic --noinput` before starting Gunicorn (or use the Docker entrypoint).

---

## 12. Startup Commands Summary

| Command | When |
|---------|------|
| `python manage.py wait_for_db` | Before migrate, if DB may not be ready |
| `python manage.py migrate --noinput` | On deploy or schema changes |
| `python manage.py collectstatic --noinput` | On deploy |
| `python manage.py validate_deployment` | Pre-deploy check |
| `gunicorn config.wsgi:application -c gunicorn.conf.py` | App server |

---

## 13. Gunicorn Configuration

`gunicorn.conf.py` can be tuned with env vars:

- `GUNICORN_BIND` – default `0.0.0.0:8000`
- `GUNICORN_WORKERS` – default `4`
- `GUNICORN_LOG_LEVEL` – default `info`

---

## 14. Backup & Recovery

Back up the database and media files regularly. Use the scripts in `scripts/`:

- **Backup**: `./scripts/backup.sh` or `.\scripts\backup.ps1` (Windows) → writes to `./backups/TIMESTAMP/`
- **Restore**: `./scripts/restore.sh ./backups/TIMESTAMP [--full]` or `.\scripts\restore.ps1 .\backups\TIMESTAMP [-Full]` (Windows)

See **[BACKUP_RECOVERY.md](BACKUP_RECOVERY.md)** for:

- Backup/restore procedures
- Scheduling recommendations (daily cron, retention)
- Recovery path for common scenarios
- Manual DB reset steps

---

## 15. Remaining Risks

| Risk | Mitigation |
|------|------------|
| DEBUG accidentally true | Base settings force DEBUG=False when SECRET_KEY is dev default |
| Migrations not applied | Entrypoint runs migrate; validate_deployment checks |
| Static 404s | WhiteNoise + collectstatic; ensure collectstatic runs |
| Celery not running | Optional; no app tasks defined; health reports Redis status |
| No HTTPS in compose | Use reverse proxy (nginx, Caddy) for TLS in front of Gunicorn |
| Media 404s in production | Reverse proxy must serve `/media/` from app volume; Django does not serve media when DEBUG=False |
| CSRF failures on HTTPS | Set `CSRF_TRUSTED_ORIGINS` to include `https://your-domain.com` |
| Large uploads | `FILE_UPLOAD_MAX_MEMORY_SIZE` defaults to 10MB; increase if needed |
| Data loss | Schedule backups (see BACKUP_RECOVERY.md); copy backups off-site |
