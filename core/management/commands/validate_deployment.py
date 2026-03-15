"""
Production deployment validation.
Run before deploy or as startup check: python manage.py validate_deployment

Validates:
- SECRET_KEY not default
- DEBUG safe for production
- ALLOWED_HOSTS configured
- DATABASE_URL reachable
- Migrations applied
- Static files collectable
"""
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Validate deployment readiness (SECRET_KEY, DEBUG, ALLOWED_HOSTS, DB, migrations)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-db",
            action="store_true",
            help="Skip database connectivity check",
        )
        parser.add_argument(
            "--skip-migrations",
            action="store_true",
            help="Skip migration check",
        )
        parser.add_argument(
            "--skip-static",
            action="store_true",
            help="Skip static files check",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail on any warning (e.g. DEBUG=true with production SECRET_KEY)",
        )

    def handle(self, *args, **options):
        errors = []
        warnings = []

        # 1. SECRET_KEY
        sk = getattr(settings, "SECRET_KEY", "")
        if not sk:
            errors.append("SECRET_KEY is empty. Set in environment.")
        elif sk in ("dev-secret-key-change-in-production", "change-this-in-production"):
            errors.append(
                "SECRET_KEY must be changed for production. "
                "Generate: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
            )
        else:
            self.stdout.write(self.style.SUCCESS("  SECRET_KEY: OK"))

        # 2. DEBUG
        debug = getattr(settings, "DEBUG", True)
        if debug and sk and sk not in ("dev-secret-key-change-in-production", "change-this-in-production"):
            warnings.append("DEBUG=True in production is unsafe. Set DEBUG=false.")
        elif not debug:
            self.stdout.write(self.style.SUCCESS("  DEBUG: OK (disabled)"))
        elif debug:
            self.stdout.write(self.style.WARNING("  DEBUG: enabled (not recommended for production)"))

        # 3. ALLOWED_HOSTS
        allowed = getattr(settings, "ALLOWED_HOSTS", [])
        if not allowed or allowed == ["*"]:
            errors.append("ALLOWED_HOSTS must be set for production (comma-separated host names).")
        elif "*" in allowed and len(allowed) == 1:
            warnings.append("ALLOWED_HOSTS=['*'] is permissive. Prefer explicit hosts.")
        else:
            self.stdout.write(self.style.SUCCESS(f"  ALLOWED_HOSTS: OK ({len(allowed)} hosts)"))

        # 4. Database
        if not options["skip_db"]:
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("  Database: connected"))
            except OperationalError as e:
                errors.append(f"Database unreachable: {e}")

        # 5. Migrations
        if not options["skip_migrations"] and not errors:
            try:
                from django.db.migrations.executor import MigrationExecutor
                executor = MigrationExecutor(connection)
                targets = executor.loader.graph.leaf_nodes()
                plan = executor.migration_plan(targets)
                if plan:
                    errors.append("Migrations pending. Run: python manage.py migrate")
                else:
                    self.stdout.write(self.style.SUCCESS("  Migrations: up to date"))
            except Exception as e:
                errors.append(f"Migrations check failed: {e}")

        # 6. Static files
        if not options["skip_static"]:
            try:
                call_command("collectstatic", "--dry-run", "--no-input", verbosity=0)
                self.stdout.write(self.style.SUCCESS("  Static files: collectable"))
            except Exception as e:
                warnings.append(f"Static collect check: {e}")

        # Fail on strict mode warnings
        if options["strict"] and warnings:
            errors.extend(warnings)
            warnings = []

        for w in warnings:
            self.stdout.write(self.style.WARNING(f"  Warning: {w}"))
        for e in errors:
            self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        if errors:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Deployment validation FAILED."))
            sys.exit(1)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Deployment validation passed."))
        sys.exit(0)
