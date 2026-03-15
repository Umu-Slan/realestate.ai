#!/bin/sh
# Production entrypoint: wait for DB, migrate, collectstatic, then exec gunicorn
set -e

echo "Waiting for database..."
python manage.py wait_for_db --timeout=60 || exit 1

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || true

echo "Starting application..."
exec "$@"
