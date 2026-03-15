#!/bin/sh
# Restore database and media from a Real Estate AI backup.
#
# Usage: ./scripts/restore.sh BACKUP_PATH [--full] [--verify]
#
#   BACKUP_PATH: path to backup directory (e.g. ./backups/20250108-120000)
#                or path to db.sql (media restore will be skipped if not in same dir)
#
#   --full:      stop app, reset DB, restore DB, restore media, start app
#                (requires postgres superuser for DROP/CREATE database)
#
#   --verify:    only verify backup integrity; do not restore. Exit 0 if valid.
#
# Without --full: restore into running stack (DB must be empty or you accept errors;
#                 media overwrites /app/media). Use for recovery to existing system.
#
# Run from project root.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker-compose.production.yml"
PG_CONTAINER="${PG_CONTAINER:-realestate_postgres_prod}"
APP_CONTAINER="${APP_CONTAINER:-realestate_app}"

# Parse args
FULL_RESTORE=false
VERIFY_ONLY=false
BACKUP_PATH=""
for arg in "$@"; do
  case "$arg" in
    --full)   FULL_RESTORE=true ;;
    --verify) VERIFY_ONLY=true ;;
    *)        BACKUP_PATH="$arg" ;;
  esac
done

if [ -z "$BACKUP_PATH" ]; then
  echo "Usage: $0 BACKUP_PATH [--full] [--verify]"
  echo "  BACKUP_PATH: directory containing db.sql (and optionally media.tar.gz)"
  echo "  --full:   stop app, reset DB, restore, restart"
  echo "  --verify: only verify backup; do not restore"
  exit 1
fi

# Resolve backup path
if [ -f "$BACKUP_PATH" ]; then
  BACKUP_DIR="$(dirname "$BACKUP_PATH")"
  DB_SQL="$BACKUP_PATH"
else
  BACKUP_DIR="$(cd "$BACKUP_PATH" 2>/dev/null || { echo "Backup path not found: $BACKUP_PATH"; exit 1; })"
  DB_SQL="$BACKUP_DIR/db.sql"
fi

if [ ! -f "$DB_SQL" ]; then
  echo "ERROR: db.sql not found at $DB_SQL"
  exit 1
fi

# --verify: run verification and exit
if [ "$VERIFY_ONLY" = true ]; then
  exec "$SCRIPT_DIR/verify_backup.sh" "$BACKUP_PATH"
fi

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export PGPASSWORD="${POSTGRES_PASSWORD:-realestate_prod}"

echo "[restore] Restoring from $BACKUP_DIR"

if [ "$FULL_RESTORE" = true ]; then
  echo "[restore] Full restore: stopping app, resetting DB..."
  docker compose -f "$COMPOSE_FILE" stop app 2>/dev/null || true
  # Drop and recreate database (postgres superuser exists in official postgres image)
  if docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='realestate_ai' AND pid <> pg_backend_pid();" 2>/dev/null; then
    docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS realestate_ai;"
    docker exec "$PG_CONTAINER" psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE realestate_ai OWNER realestate;"
  else
    echo "[restore] Trying realestate user for DB reset..."
    docker exec "$PG_CONTAINER" psql -U realestate -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='realestate_ai' AND pid <> pg_backend_pid();" 2>/dev/null || true
    docker exec "$PG_CONTAINER" psql -U realestate -d postgres -c "DROP DATABASE IF EXISTS realestate_ai;" || { echo "[restore] ERROR: Cannot reset DB. Use manual steps in BACKUP_RECOVERY.md"; exit 1; }
    docker exec "$PG_CONTAINER" psql -U realestate -d postgres -c "CREATE DATABASE realestate_ai OWNER realestate;"
  fi
fi

# 1. Restore database
echo "[restore] Restoring database..."
docker exec -i "$PG_CONTAINER" psql -U realestate realestate_ai -v ON_ERROR_STOP=1 < "$DB_SQL" || {
  echo "[restore] ERROR: Database restore failed. If DB had existing data, use --full or manually drop/create first." >&2
  exit 1
}
echo "[restore] Database restored."

# 2. Restore media (if present)
if [ -f "$BACKUP_DIR/media.tar.gz" ]; then
  echo "[restore] Restoring media files..."
  # Option A: copy into app container (app can be running)
  if docker ps -q -f name="$APP_CONTAINER" 2>/dev/null | grep -q .; then
    MEDIA_TMP="./.restore_media_$$"
    mkdir -p "$MEDIA_TMP"
    tar xzf "$BACKUP_DIR/media.tar.gz" -C "$MEDIA_TMP"
    docker cp "$MEDIA_TMP/." "$APP_CONTAINER:/app/media/"
    rm -rf "$MEDIA_TMP"
    echo "[restore] Media restored (into app container)."
  else
    # Option B: app not running, write directly to volume
    VOLUME_NAME="$(docker volume ls -q 2>/dev/null | grep -E 'media_prod_data$|_media_prod_data$' | head -1)"
    if [ -n "$VOLUME_NAME" ]; then
      docker run --rm \
        -v "$VOLUME_NAME":/data \
        -v "$BACKUP_DIR":/backup:ro \
        alpine sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; tar xzf /backup/media.tar.gz -C /data"
      echo "[restore] Media restored (into volume)."
    else
      echo "[restore] WARNING: Could not restore media (app stopped and volume not found)." >&2
    fi
  fi
else
  echo "[restore] No media.tar.gz found; skipping media."
fi

if [ "$FULL_RESTORE" = true ]; then
  echo "[restore] Starting app..."
  docker compose -f "$COMPOSE_FILE" start app 2>/dev/null || docker compose -f "$COMPOSE_FILE" up -d app
fi

echo "[restore] Done. Verify with: curl http://localhost:8000/health/ready/"
