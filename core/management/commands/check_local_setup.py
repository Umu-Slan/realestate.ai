"""
Verify local setup for PostgreSQL, .env, DATABASE_URL, and pgvector.
Run: python manage.py check_local_setup

Outputs clear diagnosis for:
- .env missing
- DATABASE_URL missing
- PostgreSQL not running
- Wrong password
- Database missing
- pgvector extension missing
"""
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Verify .env, DATABASE_URL, PostgreSQL connection, and pgvector"

    def handle(self, *args, **options):
        self.stdout.write("=== Local Setup Check ===\n")

        base_dir = Path(settings.BASE_DIR)
        env_file = base_dir / ".env"

        # 1. .env exists
        if not env_file.exists():
            self.stdout.write(self.style.WARNING("  .env file: MISSING"))
            self._fail(
                "Create .env from .env.example:\n"
                "    copy .env.example .env\n"
                "For Docker: no edits needed. For host PostgreSQL: set DATABASE_URL."
            )
        self.stdout.write(self.style.SUCCESS("  .env file: OK"))

        # 2. DATABASE_URL presence (from settings - env or default)
        db = settings.DATABASES.get("default", {})
        engine = db.get("ENGINE", "")
        if "postgresql" not in engine:
            self.stdout.write(self.style.WARNING(f"  Database engine: {engine}"))
            self._fail("This project requires PostgreSQL. Set DATABASE_URL in .env.")

        # Show config (no password)
        host = db.get("HOST", "localhost")
        port = db.get("PORT", 5432)
        name = db.get("NAME", "")
        user = db.get("USER", "")
        self.stdout.write(f"  Host: {host}, Port: {port}, DB: {name}, User: {user}")

        # 3. Attempt connection
        self.stdout.write("\n  Testing PostgreSQL connection...")
        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS("  Connection: OK"))
        except OperationalError as e:
            err_msg = str(e).lower()
            if "connection refused" in err_msg or "could not connect" in err_msg or "actively refused" in err_msg:
                self._fail(
                    "PostgreSQL is not running or not reachable.\n"
                    "  - Docker (recommended): docker compose up -d  → see docs/DOCKER_LOCAL.md\n"
                    "  - Host PostgreSQL: Start service (net start postgresql-x64-14) or see docs/POSTGRESQL_SETUP_WINDOWS.md\n"
                    "  - Check host/port in DATABASE_URL."
                )
            if "password authentication failed" in err_msg:
                self._fail(
                    "Password authentication failed. The password in DATABASE_URL does not match PostgreSQL.\n"
                    "  - RECOMMENDED: Use Docker (no host PostgreSQL needed): docker compose up -d → see docs/DOCKER_LOCAL.md\n"
                    "  - Host PostgreSQL: See docs/POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md to reset or create user.\n"
                    "  - Edit .env and set DATABASE_URL with the correct password.\n"
                    "  - Run: python manage.py print_db_config (to verify host/port/db/user)"
                )
            if "does not exist" in err_msg or "database" in err_msg and "exist" in err_msg:
                self._fail(
                    "Database does not exist. Create it:\n"
                    '  psql -U postgres -c "CREATE DATABASE realestate_ai;"\n'
                    "  Then run this check again."
                )
            self._fail(f"PostgreSQL error: {e}")

        # 4. pgvector extension
        self.stdout.write("  Checking pgvector extension...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
                row = cursor.fetchone()
            if row and row[0] == 1:
                self.stdout.write(self.style.SUCCESS("  pgvector: OK"))
            else:
                self.stdout.write(self.style.WARNING("  pgvector: NOT INSTALLED"))
                self.stdout.write(
                    self.style.WARNING(
                        "  Run: psql -U postgres -d realestate_ai -c \"CREATE EXTENSION IF NOT EXISTS vector;\"\n"
                        "  Migrations will also create it automatically if pgvector is installed on the server."
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  pgvector check failed: {e}"))

        self.stdout.write("\n" + self.style.SUCCESS("Setup check complete. You can run: python manage.py migrate"))
        sys.exit(0)

    def _fail(self, message):
        self.stdout.write("")
        self.stdout.write(self.style.ERROR(f"DIAGNOSIS:\n{message}"))
        self.stdout.write("\n  See docs/DOCKER_LOCAL.md (Docker) or docs/POSTGRESQL_SETUP_WINDOWS.md (host PostgreSQL).")
        sys.exit(1)
