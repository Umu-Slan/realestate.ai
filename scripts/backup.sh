#!/bin/sh
# Backup database and media for Real Estate AI production deployment.
# Usage: ./scripts/backup.sh [BACKUP_DIR]
#   BACKUP_DIR defaults to ./backups (relative to project root)
#
# Run from project root with production stack running:
#   docker compose -f docker-compose.production.yml up -d
#   ./scripts/backup.sh
#
# Or: BACKUP_DIR=/var/backups/realestate ./scripts/backup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="${1:-${BACKUP_DIR:-./backups}}"
# Resolve to absolute path for Docker mount
BACKUP_DIR="$(cd "$BACKUP_DIR" 2>/dev/null || mkdir -p "$BACKUP_DIR" && cd "$BACKUP_DIR" && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
COMPOSE_FILE="docker-compose.production.yml"

# Container names (must match docker-compose.production.yml)
PG_CONTAINER="${PG_CONTAINER:-realestate_postgres_prod}"
APP_CONTAINER="${APP_CONTAINER:-realestate_app}"

# Load .env for POSTGRES_PASSWORD if available
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export PGPASSWORD="${POSTGRES_PASSWORD:-realestate_prod}"

echo "[backup] Starting backup at $TIMESTAMP"
echo "[backup] Backup directory: $BACKUP_DIR"

# Ensure backup dir exists
mkdir -p "$BACKUP_DIR/$TIMESTAMP"

# 1. Database backup (plain SQL for portability)
echo "[backup] Backing up database..."
if docker exec "$PG_CONTAINER" pg_dump -U realestate realestate_ai -Fp > "$BACKUP_DIR/$TIMESTAMP/db.sql" 2>/dev/null; then
  echo "[backup] Database backup: $BACKUP_DIR/$TIMESTAMP/db.sql"
else
  echo "[backup] ERROR: Database backup failed. Is the postgres container running?" >&2
  rm -rf "$BACKUP_DIR/$TIMESTAMP"
  exit 1
fi

# 2. Media backup (operator uploads, docs, knowledge files)
echo "[backup] Backing up media files..."
MEDIA_TMP="$BACKUP_DIR/$TIMESTAMP/.media_tmp"
mkdir -p "$MEDIA_TMP"
if docker cp "$APP_CONTAINER:/app/media/." "$MEDIA_TMP" 2>/dev/null; then
  tar czf "$BACKUP_DIR/$TIMESTAMP/media.tar.gz" -C "$MEDIA_TMP" .
  rm -rf "$MEDIA_TMP"
  echo "[backup] Media backup: $BACKUP_DIR/$TIMESTAMP/media.tar.gz"
else
  rm -rf "$MEDIA_TMP"
  # Fallback: use volume directly (works when app is stopped; volume name from compose)
  VOLUME_NAME="$(docker volume ls -q 2>/dev/null | grep -E 'media_prod_data$|_media_prod_data$' | head -1)"
  if [ -n "$VOLUME_NAME" ] && docker run --rm \
    -v "$VOLUME_NAME":/data:ro \
    -v "$BACKUP_DIR/$TIMESTAMP":/out \
    alpine tar czf /out/media.tar.gz -C /data . 2>/dev/null; then
    echo "[backup] Media backup (from volume): $BACKUP_DIR/$TIMESTAMP/media.tar.gz"
  else
    echo "[backup] WARNING: Media backup skipped (app not running and volume not found)." >&2
  fi
fi

# 3. Gather metadata for manifest
ENVIRONMENT="${DJANGO_ENV:-production}"
DB_NAME="realestate_ai"
BACKUP_TYPE="full"
GIT_COMMIT=""
GIT_DESCRIBE=""
[ -d .git ] && GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null)" && GIT_DESCRIBE="$(git describe --tags --always 2>/dev/null)"

ARTIFACTS="db.sql"
[ -f "$BACKUP_DIR/$TIMESTAMP/media.tar.gz" ] && ARTIFACTS="$ARTIFACTS, media.tar.gz"

# Record counts (approx, from pg_stat_user_tables)
RECORD_COUNTS=""
RECORD_COUNTS="$(docker exec "$PG_CONTAINER" psql -U realestate "$DB_NAME" -t -A -F'|' -c "SELECT relname, COALESCE(n_live_tup::text, '0') FROM pg_stat_user_tables ORDER BY n_live_tup DESC NULLS LAST LIMIT 20;" 2>/dev/null)" || true
TOTAL_ROWS=""
TOTAL_ROWS="$(docker exec "$PG_CONTAINER" psql -U realestate "$DB_NAME" -t -c "SELECT COALESCE(SUM(n_live_tup), 0)::bigint FROM pg_stat_user_tables;" 2>/dev/null | tr -d ' \n' || echo "n/a")"

# 4. Write manifest
MANIFEST_FILE="$BACKUP_DIR/$TIMESTAMP/manifest.txt"
{
  echo "=============================================================================="
  echo "Real Estate AI Backup Manifest"
  echo "=============================================================================="
  echo ""
  echo "timestamp:           $TIMESTAMP"
  echo "date:               $(date 2>/dev/null || echo "unknown")"
  echo "environment:        $ENVIRONMENT"
  echo "database:           $DB_NAME"
  echo "backup_type:        $BACKUP_TYPE"
  echo "app_version:        ${GIT_DESCRIBE:-n/a}"
  echo "git_commit:         ${GIT_COMMIT:-n/a}"
  echo "company:            ${COMPANY_NAME:-n/a}"
  echo ""
  echo "included_artifacts: $ARTIFACTS"
  echo ""
  echo "record_counts (approx):"
  if [ -n "$RECORD_COUNTS" ]; then
    echo "$RECORD_COUNTS" | while IFS='|' read -r tbl cnt; do
      [ -n "$tbl" ] && printf "  %-35s %s\n" "$tbl" "$cnt"
    done
    echo "  --"
    echo "  total_rows: ${TOTAL_ROWS:-n/a}"
  else
    echo "  (unavailable)"
  fi
  echo ""
  echo "restore_notes:"
  echo "  Standard restore:  ./scripts/restore.sh $BACKUP_DIR/$TIMESTAMP"
  echo "  Full restore:      ./scripts/restore.sh $BACKUP_DIR/$TIMESTAMP --full"
  echo "  See BACKUP_RECOVERY.md for manual procedures."
  echo ""
  echo "=============================================================================="
} > "$MANIFEST_FILE"

# 5. Post-backup verification
echo "[backup] Verifying backup..."
if "$SCRIPT_DIR/verify_backup.sh" "$BACKUP_DIR/$TIMESTAMP"; then
  echo "[backup] Done. Backup in $BACKUP_DIR/$TIMESTAMP (verified)"
else
  echo "[backup] WARNING: Verification failed. Review backup before relying on it." >&2
  exit 1
fi
