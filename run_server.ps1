# Start Django development server for Real Estate AI Console
# Run from project root: .\run_server.ps1

Set-Location $PSScriptRoot

Write-Host "Real Estate AI - Development Server" -ForegroundColor Cyan
Write-Host "BEFORE: Ensure PostgreSQL is running (docker compose up -d)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting at http://127.0.0.1:8000/console/" -ForegroundColor Green
Write-Host "Login: http://127.0.0.1:8000/accounts/login/" -ForegroundColor Cyan
Write-Host "Create admin: python manage.py createsuperuser" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
