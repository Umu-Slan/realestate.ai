"""
One-command demo startup: migrate, seed, load users/scenarios/data, optionally run server.
Run: python manage.py run_demo
"""
import sys

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "One-command demo startup: migrate, seed, load all, optionally run server"

    def add_arguments(self, parser):
        parser.add_argument("--no-server", action="store_true", help="Do not start the server")
        parser.add_argument("--skip-migrate", action="store_true", help="Skip migrations")

    def handle(self, *args, **options):
        self.stdout.write("=== Egyptian Real Estate AI v0 Demo ===")
        self.stdout.write("")

        skip_migrate = options.get("skip_migrate", False)
        if not skip_migrate:
            # Preflight: fail gracefully if Docker services are not up
            try:
                connection.ensure_connection()
            except OperationalError:
                self.stdout.write(self.style.ERROR("PostgreSQL is not reachable."))
                self.stdout.write("")
                self.stdout.write("  Ensure Docker services are running:")
                self.stdout.write("    docker compose up -d")
                self.stdout.write("")
                self.stdout.write("  Then wait for DB and retry:")
                self.stdout.write("    python manage.py wait_for_db")
                self.stdout.write("    python manage.py run_demo")
                self.stdout.write("")
                self.stdout.write("  Or diagnose: python manage.py check_local_setup")
                sys.exit(1)
            self._run("migrate", "Migrations")
        else:
            self.stdout.write("Skipping migrations (--skip-migrate)")

        self._run("make_demo_ready", "Seed data", skip_migrate=skip_migrate)
        self._run("load_demo_users", "Demo users")
        self._run("load_demo_scenarios", "Demo scenarios")
        self._run("load_demo_data", "Sample conversations")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo environment ready."))
        self.stdout.write("")
        self.stdout.write("  Console:  http://localhost:8000/console/")
        self.stdout.write("  Admin:    http://localhost:8000/admin/")
        self.stdout.write("  Health:   http://localhost:8000/health/")
        self.stdout.write("  Credentials: operator / demo123!")
        self.stdout.write("")

        if not options["no_server"]:
            self.stdout.write("Starting server... (Ctrl+C to stop)")
            self.stdout.write("")
            call_command("runserver")
        else:
            self.stdout.write("Run server with: python manage.py runserver")

    def _run(self, cmd: str, label: str, **kwargs):
        try:
            self.stdout.write(f"  {label}... ", ending="")
            call_command(cmd, **kwargs)
            self.stdout.write(self.style.SUCCESS("OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"FAILED: {e}"))
            if cmd == "migrate":
                self.stdout.write("")
                self.stdout.write("  Ensure Docker: docker compose up -d")
                self.stdout.write("  Then: python manage.py wait_for_db")
                self.stdout.write("  Or: python manage.py check_local_setup")
                sys.exit(1)
            raise
