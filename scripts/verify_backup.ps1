# Verify a Real Estate AI backup directory.
# Usage: .\scripts\verify_backup.ps1 -BackupPath <path>
#
# Checks: db.sql exists and non-empty, manifest.txt exists,
#         media.tar.gz non-empty when present.
# Exit: 0 if valid, 1 if invalid.

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

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
    $BackupDir = [System.IO.Path]::GetFullPath($BackupPath)
    $DbSql = Join-Path $BackupDir "db.sql"
}

$Fail = $false

# db.sql: required, non-empty
if (-not (Test-Path $DbSql)) {
    Write-Host "[verify] FAIL: db.sql not found"
    $Fail = $true
} elseif ((Get-Item $DbSql).Length -eq 0) {
    Write-Host "[verify] FAIL: db.sql is empty"
    $Fail = $true
} else {
    $Size = (Get-Item $DbSql).Length
    Write-Host "[verify] OK:   db.sql exists ($Size bytes)"
}

# manifest.txt: required
$ManifestPath = Join-Path $BackupDir "manifest.txt"
if (-not (Test-Path $ManifestPath)) {
    Write-Host "[verify] FAIL: manifest.txt not found"
    $Fail = $true
} else {
    Write-Host "[verify] OK:   manifest.txt exists"
}

# media.tar.gz: optional but if present must be non-empty
$MediaPath = Join-Path $BackupDir "media.tar.gz"
if (Test-Path $MediaPath) {
    if ((Get-Item $MediaPath).Length -eq 0) {
        Write-Host "[verify] WARN: media.tar.gz exists but is empty"
    } else {
        $Size = (Get-Item $MediaPath).Length
        Write-Host "[verify] OK:   media.tar.gz exists ($Size bytes)"
    }
} else {
    Write-Host "[verify] OK:   media.tar.gz not present (optional)"
}

# Quick sanity: db.sql should start with PostgreSQL dump header
if ((Test-Path $DbSql) -and ((Get-Item $DbSql).Length -gt 0)) {
    $FirstLine = Get-Content $DbSql -First 1 -ErrorAction SilentlyContinue
    if ($FirstLine -match "PostgreSQL database dump") {
        Write-Host "[verify] OK:   db.sql has valid PostgreSQL dump header"
    } else {
        Write-Host "[verify] WARN: db.sql may not be a valid pg_dump (header missing)"
    }
}

Write-Host ""
if ($Fail) {
    Write-Host "[verify] Backup INVALID - do not use for restore"
    exit 1
} else {
    Write-Host "[verify] Backup VALID"
    exit 0
}
