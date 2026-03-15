@echo off
cd /d "%~dp0"

echo Real Estate AI - Development Server
echo.
echo BEFORE: Ensure PostgreSQL is running (docker compose up -d)
echo.
echo Starting at http://127.0.0.1:8000/console/
echo.
echo Login: http://127.0.0.1:8000/accounts/login/
echo Create admin: python manage.py createsuperuser
echo.
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
