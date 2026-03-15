# Local Development Guide

## Prerequisites

- Python 3.11+
- **Recommended**: Docker Desktop (PostgreSQL + Redis)
- **Alternative**: Host PostgreSQL 14+ with pgvector, Redis (optional)

---

## Recommended: Docker-Based Setup (No Host PostgreSQL)

**→ [docs/DOCKER_LOCAL.md](DOCKER_LOCAL.md)**

No host PostgreSQL or password needed:

```powershell
docker compose up -d
.venv\Scripts\activate
python manage.py wait_for_db
python manage.py migrate
python manage.py run_demo
```

First time: `copy .env.example .env` (no edits). Or run `.\scripts\start-demo.ps1`.

---

## Alternative: Host PostgreSQL Setup

If you prefer or cannot use Docker:

### Troubleshooting: Unknown PostgreSQL Password

If `check_local_setup` reports **"password authentication failed"** and you do not know the `postgres` password:

→ **[docs/POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md](POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md)**

Or use Docker instead (see above).

### First-Time Setup (Host PostgreSQL)

1. Install and start PostgreSQL — see [POSTGRESQL_SETUP_WINDOWS.md](POSTGRESQL_SETUP_WINDOWS.md)
2. Create database: `psql -U postgres -c "CREATE DATABASE realestate_ai;"`
3. pgvector: `psql -U postgres -d realestate_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"`
4. Project setup:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   # Edit .env: set DATABASE_URL with your PostgreSQL credentials
   ```
5. Verify: `python manage.py check_local_setup`
6. Migrate and run: `python manage.py migrate` then `python manage.py run_demo`

## Quick Start (After First-Time Setup)

```powershell
.venv\Scripts\activate
# If Docker: docker compose up -d
# If host PostgreSQL: ensure service is running
python manage.py run_demo
```

## Demo Credentials

| User     | Password  | Role     |
|----------|-----------|----------|
| admin    | demo123!  | Admin    |
| operator | demo123!  | Operator |
| reviewer | demo123!  | Reviewer |
| demo     | demo123!  | Read-only|

## Health Checks

- http://localhost:8000/health/ - Aggregated status
- http://localhost:8000/health/db/
- http://localhost:8000/health/redis/
- http://localhost:8000/health/vector/
- http://localhost:8000/health/model/

## Console & Demo

- Operator Console: http://localhost:8000/console/
- Demo Eval: http://localhost:8000/console/demo/eval/
- Admin: http://localhost:8000/admin/

## Without Redis

For a minimal local demo, Redis is optional. Celery won't run, but the app will work. Health/redis will report fail; health/ will still pass if DB and vector are ok.
