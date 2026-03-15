# Restore database and media from a Real Estate AI backup.
#
# Usage: .\scripts\restore.ps1 -BackupPath <path> [-Full] [-Verify]
#
#   BackupPath: path to backup directory (e.g. .\backups\20250108-120000)
#               or path to db.sql (media restore skipped if not in same dir)
#
#   -Full:      stop app, reset DB, restore DB, restore media, start app
#               (requires postgres superuser for DROP/CREATE database)
#
#   -Verify:    only verify backup integrity; do not restore. Exit 0 if valid.
#
# Without -Full: restore into running stack (DB must be empty or you accept errors;
#               media overwrites /app/media).
#
# Run from project root.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BackupPath,
    [switch]$Full,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$ComposeFile = "docker-compose.production.yml"
$PgContainer = if ($env:PG_CONTAINER) { $env:PG_CONTAINER } else { "realestate_postgres_prod" }
$AppContainer = if ($env:APP_CONTAINER) { $env:APP_CONTAINER } else { "realestate_app" }

# Resolve backup path
if (-not [System.IO.Path]::IsPathRooted($BackupPath)) {
    $BackupPath = Join-Path $ProjectRoot $BackupPath
}
$BackupPath = [System.IO.Path]::GetFullPath($BackupPath)

$BackupDir = $null
$DbSql = $null
if (Test-Path $BackupPath -PathType Leaf) {
    $BackupDir = Split-Path -Parent $BackupPath
    $DbSql = $BackupPath
} else {
    $BackupDir = $BackupPath
    $DbSql = Join-Path $BackupDir "db.sql"
}

if (-not (Test-Path $DbSql)) {
    Write-Error "ERROR: db.sql not found at $DbSql"
    exit 1
}

# -Verify: run verification and exit
if ($Verify) {
    & $ScriptDir\verify_backup.ps1 -BackupPath $BackupPath
    exit $LASTEXITCODE
}

# Load .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}
$env:PGPASSWORD = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "realestate_prod" }

Write-Host "[restore] Restoring from $BackupDir"

if ($Full) {
    Write-Host "[restore] Full restore: stopping app, resetting DB..."
    docker compose -f $ComposeFile stop app 2>$null
    docker exec $PgContainer psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='realestate_ai' AND pid <> pg_backend_pid();" 2>$null
    docker exec $PgContainer psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS realestate_ai;"
    docker exec $PgContainer psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE realestate_ai OWNER realestate;"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[restore] Trying realestate user for DB reset..."
        docker exec $PgContainer psql -U realestate -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='realestate_ai' AND pid <> pg_backend_pid();" 2>$null
        docker exec $PgContainer psql -U realestate -d postgres -c "DROP DATABASE IF EXISTS realestate_ai;"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "[restore] ERROR: Cannot reset DB. Use manual steps in BACKUP_RECOVERY.md"
            exit 1
        }
        docker exec $PgContainer psql -U realestate -d postgres -c "CREATE DATABASE realestate_ai OWNER realestate;"
    }
}

# 1. Restore database (stream via cmd to avoid loading large file into memory)
Write-Host "[restore] Restoring database..."
$DbSqlQuoted = "`"$DbSql`""
cmd /c "docker exec -i $PgContainer psql -U realestate realestate_ai -v ON_ERROR_STOP=1 < $DbSqlQuoted"
if ($LASTEXITCODE -ne 0) {
    Write-Error "[restore] ERROR: Database restore failed. If DB had existing data, use -Full or manually drop/create first."
    exit 1
}
Write-Host "[restore] Database restored."

# 2. Restore media (if present)
$MediaPath = Join-Path $BackupDir "media.tar.gz"
if (Test-Path $MediaPath) {
    Write-Host "[restore] Restoring media files..."
    $AppRunning = docker ps -q -f "name=$AppContainer" 2>$null
    if ($AppRunning) {
        $MediaTmp = Join-Path $ProjectRoot ".restore_media_$PID"
        New-Item -ItemType Directory -Path $MediaTmp -Force | Out-Null
        try {
            tar -xzf $MediaPath -C $MediaTmp
            docker cp "${MediaTmp}/." "${AppContainer}:/app/media/"
            Write-Host "[restore] Media restored (into app container)."
        } finally {
            Remove-Item -Path $MediaTmp -Recurse -Force -ErrorAction SilentlyContinue
        }
    } else {
        $VolumeName = docker volume ls -q 2>$null | Select-String -Pattern "media_prod_data" | Select-Object -First 1
        if ($VolumeName) {
            $VolPath = $VolumeName.ToString().Trim()
            docker run --rm -v "${VolPath}:/data" -v "${BackupDir}:/backup:ro" alpine sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; tar xzf /backup/media.tar.gz -C /data"
            Write-Host "[restore] Media restored (into volume)."
        } else {
            Write-Warning "[restore] WARNING: Could not restore media (app stopped and volume not found)."
        }
    }
} else {
    Write-Host "[restore] No media.tar.gz found; skipping media."
}

if ($Full) {
    Write-Host "[restore] Starting app..."
    docker compose -f $ComposeFile start app 2>$null
    if ($LASTEXITCODE -ne 0) { docker compose -f $ComposeFile up -d app }
}

Write-Host "[restore] Done. Verify with: curl http://localhost:8000/health/ready/"
