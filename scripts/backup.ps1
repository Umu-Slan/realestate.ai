# Backup database and media for Real Estate AI production deployment.
# Usage: .\scripts\backup.ps1 [-BackupDir <path>]
#   BackupDir defaults to .\backups (relative to project root)
#
# Run from project root with production stack running:
#   docker compose -f docker-compose.production.yml up -d
#   .\scripts\backup.ps1
#
# Or: .\scripts\backup.ps1 -BackupDir C:\backups\realestate

param(
    [Parameter(Position = 0)]
    [string]$BackupDir = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($BackupDir)) {
    $BackupDir = Join-Path $ProjectRoot "backups"
}
$BackupDir = [System.IO.Path]::GetFullPath($BackupDir)
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$PgContainer = if ($env:PG_CONTAINER) { $env:PG_CONTAINER } else { "realestate_postgres_prod" }
$AppContainer = if ($env:APP_CONTAINER) { $env:APP_CONTAINER } else { "realestate_app" }

# Load .env for POSTGRES_PASSWORD
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

Write-Host "[backup] Starting backup at $Timestamp"
Write-Host "[backup] Backup directory: $BackupDir"

$TimestampDir = Join-Path $BackupDir $Timestamp
New-Item -ItemType Directory -Path $TimestampDir -Force | Out-Null

# 1. Database backup
Write-Host "[backup] Backing up database..."
$DbSqlPath = Join-Path $TimestampDir "db.sql"
try {
    docker exec $PgContainer pg_dump -U realestate realestate_ai -Fp 2>$null | Out-File -FilePath $DbSqlPath -Encoding ASCII
    if ((Get-Item $DbSqlPath).Length -eq 0) { throw "db.sql is empty" }
    Write-Host "[backup] Database backup: $TimestampDir\db.sql"
} catch {
    Write-Error "[backup] ERROR: Database backup failed. Is the postgres container running?"
    Remove-Item -Path $TimestampDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# 2. Media backup
Write-Host "[backup] Backing up media files..."
$MediaTmp = Join-Path $TimestampDir ".media_tmp"
New-Item -ItemType Directory -Path $MediaTmp -Force | Out-Null
$MediaBackedUp = $false
try {
    docker cp "${AppContainer}:/app/media/." $MediaTmp 2>$null
    if ($LASTEXITCODE -eq 0) {
        $MediaArchive = Join-Path $TimestampDir "media.tar.gz"
        tar -czf $MediaArchive -C $MediaTmp .
        Remove-Item -Path $MediaTmp -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[backup] Media backup: $MediaArchive"
        $MediaBackedUp = $true
    }
} catch { }
if (-not $MediaBackedUp) {
    Remove-Item -Path $MediaTmp -Recurse -Force -ErrorAction SilentlyContinue
    $VolumeName = docker volume ls -q 2>$null | Select-String -Pattern "media_prod_data" | Select-Object -First 1
    if ($VolumeName) {
        try {
            docker run --rm -v "${VolumeName}:/data:ro" -v "${TimestampDir}:/out" alpine tar czf /out/media.tar.gz -C /data . 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[backup] Media backup (from volume): $TimestampDir\media.tar.gz"
                $MediaBackedUp = $true
            }
        } catch { }
    }
    if (-not $MediaBackedUp) {
        Write-Warning "[backup] WARNING: Media backup skipped (app not running and volume not found)."
    }
}

# 3. Gather metadata for manifest
$EnvName = if ($env:DJANGO_ENV) { $env:DJANGO_ENV } else { "production" }
$DbName = "realestate_ai"
$BackupType = "full"
$GitCommit = ""
$GitDescribe = ""
if (Test-Path ".git") {
    $GitCommit = git rev-parse HEAD 2>$null
    $GitDescribe = git describe --tags --always 2>$null
}
$Artifacts = "db.sql"
if (Test-Path (Join-Path $TimestampDir "media.tar.gz")) { $Artifacts = "db.sql, media.tar.gz" }

$RecordCounts = ""
$TotalRows = "n/a"
try {
    $RecordCounts = docker exec $PgContainer psql -U realestate $DbName -t -A -F'|' -c "SELECT relname, COALESCE(n_live_tup::text, '0') FROM pg_stat_user_tables ORDER BY n_live_tup DESC NULLS LAST LIMIT 20;" 2>$null
    $TotalRows = (docker exec $PgContainer psql -U realestate $DbName -t -c "SELECT COALESCE(SUM(n_live_tup), 0)::bigint FROM pg_stat_user_tables;" 2>$null) -replace '\s', ''
    if ([string]::IsNullOrWhiteSpace($TotalRows)) { $TotalRows = "n/a" }
} catch { }

# 4. Write manifest
$ManifestPath = Join-Path $TimestampDir "manifest.txt"
$ManifestLines = @(
    "==============================================================================",
    "Real Estate AI Backup Manifest",
    "==============================================================================",
    "",
    "timestamp:           $Timestamp",
    "date:               $(Get-Date)",
    "environment:        $EnvName",
    "database:           $DbName",
    "backup_type:        $BackupType",
    "app_version:        $(if ($GitDescribe) { $GitDescribe } else { 'n/a' })",
    "git_commit:         $(if ($GitCommit) { $GitCommit } else { 'n/a' })",
    "company:            $(if ($env:COMPANY_NAME) { $env:COMPANY_NAME } else { 'n/a' })",
    "",
    "included_artifacts: $Artifacts",
    "",
    "record_counts (approx):"
)
if ($RecordCounts) {
    $RecordCounts -split "`n" | ForEach-Object {
        $parts = $_ -split '\|'
        if ($parts.Length -ge 2) { $ManifestLines += "  $($parts[0].PadRight(35)) $($parts[1])" }
    }
    $ManifestLines += "  --"
    $ManifestLines += "  total_rows: $TotalRows"
} else {
    $ManifestLines += "  (unavailable)"
}
$ManifestLines += @(
    "",
    "restore_notes:",
    "  Standard restore:  .\scripts\restore.ps1 $TimestampDir",
    "  Full restore:      .\scripts\restore.ps1 -BackupPath $TimestampDir -Full",
    "  See BACKUP_RECOVERY.md for manual procedures.",
    "",
    "=============================================================================="
)
$ManifestLines | Set-Content -Path $ManifestPath -Encoding UTF8

# 5. Post-backup verification
Write-Host "[backup] Verifying backup..."
& $ScriptDir\verify_backup.ps1 -BackupPath $TimestampDir
if ($LASTEXITCODE -eq 0) {
    Write-Host "[backup] Done. Backup in $TimestampDir (verified)"
} else {
    Write-Error "[backup] WARNING: Verification failed. Review backup before relying on it."
    exit 1
}
