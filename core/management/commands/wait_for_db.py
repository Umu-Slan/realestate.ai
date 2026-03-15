"""
Poll until PostgreSQL is ready. Useful after docker compose up -d.
Run: python manage.py wait_for_db
"""
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Poll until PostgreSQL is ready (e.g. after docker compose up)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Seconds to wait before giving up (default: 60)",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Seconds between retries (default: 2)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        db = settings.DATABASES.get("default", {})
        host = db.get("HOST", "localhost")
        port = db.get("PORT", 5432)
        name = db.get("NAME", "")

        self.stdout.write(f"Waiting for PostgreSQL at {host}:{port}/{name} (timeout={timeout}s)...")

        start = time.monotonic()
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("PostgreSQL is ready."))
                return
            except OperationalError:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Timeout after {timeout}s. Is PostgreSQL running?\n"
                            "  Docker: docker compose up -d\n"
                            "  See: docs/DOCKER_LOCAL.md"
                        )
                    )
                    sys.exit(1)
                self.stdout.write(f"  Retrying in {interval}s... ({int(elapsed)}s elapsed)")
                time.sleep(interval)
