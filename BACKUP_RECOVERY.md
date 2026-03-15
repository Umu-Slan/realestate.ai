# Backup & Recovery

Operational procedures for backing up and recovering Real Estate AI company data.

---

## 1. What Gets Backed Up

| Data | Location | Backup method |
|------|----------|---------------|
| **Database** | PostgreSQL `realestate_ai` | `pg_dump` → plain SQL |
| **Media files** | Operator uploads, docs, knowledge files | `tar.gz` of `/app/media` |

**Redis** is not backed up; it holds ephemeral cache/Celery data and is not required for recovery.

---

## 2. Backup

### 2.1 Run a Backup

From the project root, with the production stack running:

**Linux / macOS / Git Bash:**
```bash
./scripts/backup.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\backup.ps1
```

Backups are written to `./backups/TIMESTAMP/` (e.g. `backups/20250108-143022/`):

- `db.sql` – database dump
- `media.tar.gz` – compressed media directory (if media backup succeeded)
- `manifest.txt` – backup manifest with metadata (see [Manifest Format](#22-manifest-format))

The backup script runs **post-backup verification** automatically. It checks that `db.sql` exists and is non-empty, `manifest.txt` exists, and `media.tar.gz` (when present) is non-empty. The script exits with an error if verification fails.

### 2.2 Manifest Format

Each backup includes a `manifest.txt` with:

| Field | Description |
|-------|-------------|
| `timestamp` | Backup run ID (YYYYMMDD-HHMMSS) |
| `date` | Human-readable backup time |
| `environment` | `DJANGO_ENV` (e.g. production) |
| `database` | Database name (realestate_ai) |
| `backup_type` | `full` (db + media) |
| `app_version` | Git describe (tag or commit) if repo present |
| `git_commit` | Full commit hash if repo present |
| `company` | `COMPANY_NAME` from `.env` if set |
| `included_artifacts` | `db.sql`, `media.tar.gz` (if present) |
| `record_counts` | Approx table row counts (top 20 + total) |
| `restore_notes` | Restore command hints |

Set `COMPANY_NAME` in `.env` to identify backups for multi-tenant or multi-company deployments.

### 2.3 Custom Backup Directory

**Linux / macOS / Git Bash:**
```bash
./scripts/backup.sh /var/backups/realestate
# or
BACKUP_DIR=/var/backups/realestate ./scripts/backup.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\backup.ps1 C:\backups\realestate
# or
.\scripts\backup.ps1 -BackupDir C:\backups\realestate
```

### 2.4 Requirements

- Docker and Docker Compose
- Production stack running (`docker compose -f docker-compose.production.yml up -d`)
- For media backup: app container running (or media volume must exist for fallback)

### 2.5 Windows-Specific Notes

| Requirement | Notes |
|-------------|-------|
| **PowerShell** | Use PowerShell 5.1 or later (Windows built-in). PowerShell Core 7+ also works. |
| **tar** | Windows 10 (1803+) and 11 include `tar`. For older Windows, use Git Bash or install tar. |
| **Execution policy** | If scripts are blocked, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` or use `-ExecutionPolicy Bypass` when invoking. |

---

## 3. Restore

### 3.1 Standard Restore (into running stack)

Use when restoring into an existing deployment or when the database is already empty:

**Linux / macOS / Git Bash:**
```bash
./scripts/restore.sh ./backups/20250108-143022
```

**Windows (PowerShell):**
```powershell
.\scripts\restore.ps1 .\backups\20250108-143022
```

- **Database**: SQL is applied to `realestate_ai`. If the DB has existing data, you may see constraint errors; use full restore for a clean slate.
- **Media**: Extracted into `/app/media`, overwriting existing files.

### 3.2 Full Restore (reset + restore)

Use for disaster recovery or when you need a clean database:

**Linux / macOS / Git Bash:**
```bash
./scripts/restore.sh ./backups/20250108-143022 --full
```

**Windows (PowerShell):**
```powershell
.\scripts\restore.ps1 .\backups\20250108-143022 -Full
```

This will:

1. Stop the app container
2. Drop and recreate the `realestate_ai` database
3. Restore the database from `db.sql`
4. Restore media from `media.tar.gz`
5. Start the app container

**Note**: DB reset requires `postgres` superuser (default in the official PostgreSQL image). If that fails, see [Manual Database Reset](#62-manual-database-reset).

### 3.3 Verify Backup Before Restore

Validate a backup without restoring:

**Linux / macOS / Git Bash:**
```bash
./scripts/restore.sh ./backups/20250108-143022 --verify
# or
./scripts/verify_backup.sh ./backups/20250108-143022
```

**Windows (PowerShell):**
```powershell
.\scripts\restore.ps1 .\backups\20250108-143022 -Verify
# or
.\scripts\verify_backup.ps1 .\backups\20250108-143022
```

Checks: `db.sql` exists and non-empty, `manifest.txt` exists, `media.tar.gz` non-empty when present. Exit 0 if valid, 1 if invalid.

### 3.4 Restore to a New Server

1. Set up Docker, clone the repo, copy `.env` with production values.
2. Start only Postgres and Redis: `docker compose -f docker-compose.production.yml up -d postgres redis`
3. Wait for health, then run full restore: `./scripts/restore.sh /path/to/backup --full` or `.\scripts\restore.ps1 C:\path\to\backup -Full`
4. Start the app: `docker compose -f docker-compose.production.yml up -d app`

---

## 4. Scheduling Recommendations

### 4.1 Suggested Schedule

| Frequency | What | Retention |
|-----------|------|-----------|
| Daily | Full backup (DB + media) | 7–14 days |
| Weekly | Full backup, copy to off-site storage | 4–8 weeks |
| Monthly | Test restore (verify a backup end-to-end) | — |

### 4.2 cron Example (Linux)

```cron
# Daily at 02:00
0 2 * * * cd /opt/realestate-ai && ./scripts/backup.sh /var/backups/realestate

# Weekly Sunday 03:00 – also copy to remote
0 3 * * 0 cd /opt/realestate-ai && ./scripts/backup.sh /var/backups/realestate && rsync -a /var/backups/realestate/ backup-server:/backups/realestate/
```

### 4.3 Windows Task Scheduler

Create a scheduled task that runs PowerShell directly:

```powershell
# Action: Start a program
# Program: powershell.exe
# Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\Realestate\scripts\backup.ps1" -BackupDir "C:\backups\realestate"
# Start in: C:\path\to\Realestate
```

Or use a wrapper batch file `backup-daily.bat`:
```batch
@echo off
cd /d C:\path\to\Realestate
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\backup.ps1 -BackupDir C:\backups\realestate
```

**Alternative**: Use Git Bash or WSL to run `./scripts/backup.sh` if PowerShell is not preferred.

---

## 5. Recovery Path (Quick Reference)

| Scenario | Steps |
|----------|-------|
| **Accidental delete** | Restore a recent backup to recover data; prefer restoring only the affected tables if possible (manual `psql`). |
| **Corrupted database** | Full restore: `./scripts/restore.sh BACKUP_DIR --full` or `.\scripts\restore.ps1 BACKUP_DIR -Full` |
| **Server failure** | New server + full restore (see §3.4). |
| **Media files lost** | Restore media only: `tar xzf BACKUP_DIR/media.tar.gz -C /tmp/media && docker cp /tmp/media/. CONTAINER:/app/media/` (or use restore script with backup that includes media). |
| **Point-in-time recovery** | Not supported; use the most recent backup before the incident. |

---

## 6. Manual Procedures

### 6.1 Manual Database Backup

**Linux / macOS / Git Bash:**
```bash
docker exec realestate_postgres_prod pg_dump -U realestate realestate_ai -Fp > backup_$(date +%Y%m%d).sql
```

**Windows (PowerShell):**
```powershell
$date = Get-Date -Format "yyyyMMdd"
docker exec realestate_postgres_prod pg_dump -U realestate realestate_ai -Fp | Out-File -FilePath "backup_$date.sql" -Encoding ASCII
```

### 6.2 Manual Database Reset

If the restore script cannot reset the DB (e.g. permissions):

```bash
# Stop app
docker compose -f docker-compose.production.yml stop app

# Connect and reset (as postgres superuser)
docker exec -it realestate_postgres_prod psql -U postgres -d postgres -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='realestate_ai' AND pid <> pg_backend_pid();
  DROP DATABASE IF EXISTS realestate_ai;
  CREATE DATABASE realestate_ai OWNER realestate;
"

# Restore
docker exec -i realestate_postgres_prod psql -U realestate realestate_ai < backups/TIMESTAMP/db.sql

# Start app
docker compose -f docker-compose.production.yml start app
```

### 6.3 Media-Only Restore

```bash
# With app running
docker cp CONTAINER:/app/media/. /tmp/current_media
tar xzf backups/TIMESTAMP/media.tar.gz -C /tmp/restore
docker cp /tmp/restore/. realestate_app:/app/media/
```

---

## 7. Verification

### 7.1 Post-Backup Verification (Automatic)

After each backup, the script runs verification (`verify_backup.sh` / `verify_backup.ps1`) and exits with an error if checks fail:

- `db.sql` – exists, non-empty
- `manifest.txt` – exists
- `media.tar.gz` – when present, non-empty
- `db.sql` – valid PostgreSQL dump header

### 7.2 Manual Verification

Verify any backup directory:

**Linux / macOS / Git Bash:**
```bash
./scripts/verify_backup.sh ./backups/20250108-143022
```

**Windows (PowerShell):**
```powershell
.\scripts\verify_backup.ps1 .\backups\20250108-143022
```

Expected output: `[verify] OK` for db.sql, manifest.txt; `Backup VALID`

### 7.3 After Restore

```bash
curl http://localhost:8000/health/ready/
curl http://localhost:8000/health/
# Log into console, verify data
```

### 7.4 Periodic Test Restores

**Recommendation**: Run a test restore at least **monthly** (or quarterly for low-change environments) to confirm backups are usable.

1. Pick a recent backup (e.g. from last week).
2. Verify it: `./scripts/verify_backup.sh ./backups/TIMESTAMP` or `.\scripts\verify_backup.ps1 .\backups\TIMESTAMP`
3. Option A (staging): Restore to a separate staging DB or container, verify data.
4. Option B (production): During a maintenance window, run full restore to a temporary DB, spot-check data, then revert if needed.

Test restores surface issues (corrupt dumps, missing media, restore script bugs) before a real disaster.

---

## 8. Remaining Risks

| Risk | Mitigation |
|------|------------|
| No point-in-time recovery | Use most recent backup; schedule frequent backups. |
| Backups on same disk as app | Copy to off-site or different storage. |
| Backup script fails silently | Post-backup verification exits 1 on failure; monitor cron output. |
| Large media slows backup | Run during low-traffic window; consider incremental for media later. |
| Backup never tested | Schedule periodic test restores (see §7.4). |
