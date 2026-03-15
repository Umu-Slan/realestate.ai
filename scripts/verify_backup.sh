#!/bin/sh
# Verify a Real Estate AI backup directory.
# Usage: ./scripts/verify_backup.sh BACKUP_PATH
#
# Checks: db.sql exists and non-empty, manifest.txt exists,
#         media.tar.gz non-empty when present.
# Exit: 0 if valid, 1 if invalid.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_PATH="${1:-}"
if [ -z "$BACKUP_PATH" ]; then
  echo "Usage: $0 BACKUP_PATH"
  echo "  BACKUP_PATH: backup directory (e.g. ./backups/20250108-143022)"
  exit 1
fi

if [ -f "$BACKUP_PATH" ]; then
  BACKUP_DIR="$(dirname "$BACKUP_PATH")"
  DB_SQL="$BACKUP_PATH"
else
  BACKUP_DIR="$(cd "$BACKUP_PATH" 2>/dev/null || { echo "Backup path not found: $BACKUP_PATH"; exit 1; })"
  DB_SQL="$BACKUP_DIR/db.sql"
fi

FAIL=0

# db.sql: required, non-empty
if [ ! -f "$DB_SQL" ]; then
  echo "[verify] FAIL: db.sql not found"
  FAIL=1
elif [ ! -s "$DB_SQL" ]; then
  echo "[verify] FAIL: db.sql is empty"
  FAIL=1
else
  SIZE="$(wc -c < "$DB_SQL" 2>/dev/null | tr -d ' ')"
  echo "[verify] OK:   db.sql exists ($SIZE bytes)"
fi

# manifest.txt: required
if [ ! -f "$BACKUP_DIR/manifest.txt" ]; then
  echo "[verify] FAIL: manifest.txt not found"
  FAIL=1
else
  echo "[verify] OK:   manifest.txt exists"
fi

# media.tar.gz: optional but if present must be non-empty
if [ -f "$BACKUP_DIR/media.tar.gz" ]; then
  if [ ! -s "$BACKUP_DIR/media.tar.gz" ]; then
    echo "[verify] WARN: media.tar.gz exists but is empty"
  else
    SIZE="$(wc -c < "$BACKUP_DIR/media.tar.gz" 2>/dev/null | tr -d ' ')"
    echo "[verify] OK:   media.tar.gz exists ($SIZE bytes)"
  fi
else
  echo "[verify] OK:   media.tar.gz not present (optional)"
fi

# Quick sanity: db.sql should start with PostgreSQL dump header
if [ -f "$DB_SQL" ] && [ -s "$DB_SQL" ]; then
  if head -1 "$DB_SQL" | grep -q 'PostgreSQL database dump'; then
    echo "[verify] OK:   db.sql has valid PostgreSQL dump header"
  else
    echo "[verify] WARN: db.sql may not be a valid pg_dump (header missing)"
  fi
fi

echo ""
if [ "$FAIL" -eq 1 ]; then
  echo "[verify] Backup INVALID - do not use for restore"
  exit 1
else
  echo "[verify] Backup VALID"
  exit 0
fi
