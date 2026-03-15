# Egyptian Real Estate AI - Local Demo Startup
# Run from project root: .\scripts\start-demo.ps1

docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\.venv\Scripts\activate
python manage.py wait_for_db
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python manage.py migrate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python manage.py run_demo
