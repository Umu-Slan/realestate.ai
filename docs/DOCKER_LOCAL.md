# Docker-Based Local Setup (Recommended)

No host PostgreSQL required. PostgreSQL (pgvector) + Redis run in Docker.

**Ports**: This project uses `localhost:5433` for PostgreSQL and `localhost:6380` for Redis to avoid conflicts with host PostgreSQL (5432) and host Redis (6379).

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- Python 3.11+

## Startup (From Scratch)

```powershell
# 1. Start infrastructure
docker compose up -d

# 2. Project setup (first time only)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# 3. Wait for PostgreSQL
python manage.py wait_for_db

# 4. Verify (optional)
python manage.py check_local_setup

# 5. Migrate and run demo
python manage.py migrate
python manage.py run_demo
```

## Quick Start (After First-Time Setup)

```powershell
docker compose up -d
.venv\Scripts\activate
python manage.py wait_for_db
python manage.py migrate
python manage.py run_demo
```

Or use the script: `.\scripts\start-demo.ps1`

## Services

| Service   | Port | Credentials                           | Internal hostname (container-to-container) |
|-----------|------|---------------------------------------|---------------------------------------------|
| PostgreSQL| 5433 | realestate_dev / realestate_dev_pass  | postgres                                    |
| Redis     | 6380 | (none)                                | redis                                       |

From your host (PowerShell, Django), use `localhost:5433` and `localhost:6380`.

*Host PostgreSQL on 5432 may conflict; this project uses 5433 for Docker Postgres.*

## .env (Docker Defaults)

`.env.example` is preconfigured for Docker. After `copy .env.example .env`, no edits needed:

```
DATABASE_URL=postgresql://realestate_dev:realestate_dev_pass@localhost:5433/realestate_ai
REDIS_URL=redis://localhost:6380/0
CELERY_BROKER_URL=redis://localhost:6380/1
```

## Troubleshooting

### Docker not running

**Symptom**: `error during connect` or `Cannot connect to the Docker daemon`

**Fix**: Start Docker Desktop (Windows/Mac) or the Docker service.

### Port 5433 already in use (PostgreSQL)

**Symptom**: `Bind for 0.0.0.0:5433 failed: port is already allocated`

**Fix**: Another service is using 5433. Change the port in `docker-compose.yml` (e.g. `"5434:5432"`) and use `DATABASE_URL=...@localhost:5434/realestate_ai` in `.env`.

*This project uses 5433 by default to avoid conflict with host PostgreSQL on 5432.*

### Port 6380 already in use (Redis)

**Symptom**: `Bind for 0.0.0.0:6380 failed: port is already allocated`

**Fix**: Another service is using 6380.
- Stop it or change the port in `docker-compose.yml` (e.g. `"6381:6379"`) and update `REDIS_URL` and `CELERY_BROKER_URL` in `.env` to `localhost:6381`.

*Note: This project uses 6380 by default to avoid conflict with host Redis on 6379.*

### pgvector missing in container

**Symptom**: `extension "vector" is not available` during migrate

**Fix**: The `pgvector/pgvector:pg16` image includes pgvector. Ensure you're using that image and the init script ran (first startup). If the volume was created with an older image, remove and recreate:

```powershell
docker compose down -v
docker compose up -d
python manage.py wait_for_db
python manage.py migrate
```

`-v` deletes volumes; data is reset.

### Containers not healthy

```powershell
docker compose ps
```

If `postgres` or `redis` shows `starting`, wait 10–15 seconds and retry. For postgres: `python manage.py wait_for_db`.

### .env still pointing to old credentials

**Symptom**: `password authentication failed` or Redis connection refused.

**Fix**: Ensure `.env` uses Docker defaults:
```
DATABASE_URL=postgresql://realestate_dev:realestate_dev_pass@localhost:5433/realestate_ai
REDIS_URL=redis://localhost:6380/0
CELERY_BROKER_URL=redis://localhost:6380/1
```
If you previously used host PostgreSQL, overwrite with `copy .env.example .env` (Docker values require no edits).

### wait_for_db timing out

**Symptom**: `Timeout after 60s. Is PostgreSQL running?`

**Fix**:
1. Ensure Docker is running: `docker compose ps` (containers should be `running`).
2. If postgres is `starting`, wait 15–20 seconds for first boot, then retry.
3. This project uses port 5433 for Docker Postgres; ensure `.env` has `localhost:5433` in DATABASE_URL.
