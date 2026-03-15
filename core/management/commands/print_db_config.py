"""
Safely print database connection config (host, port, db, user) — never prints password.
Run: python manage.py print_db_config
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print database config (host, port, db, user) without password"

    def handle(self, *args, **options):
        db = settings.DATABASES.get("default", {})
        host = db.get("HOST", "localhost")
        port = db.get("PORT", 5432)
        name = db.get("NAME", "")
        user = db.get("USER", "")

        self.stdout.write("Database config (from DATABASE_URL / .env):")
        self.stdout.write(f"  Host:     {host}")
        self.stdout.write(f"  Port:     {port}")
        self.stdout.write(f"  Database: {name}")
        self.stdout.write(f"  User:     {user}")
        self.stdout.write("  Password: [not printed]")

        self.stdout.write("\nTo fix connection issues:")
        self.stdout.write("  1. Ensure PostgreSQL is running.")
        self.stdout.write("  2. Edit .env and set DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB")
        self.stdout.write("  3. Run: python manage.py check_local_setup")
        self.stdout.write("\nIf you do not know the PostgreSQL password:")
        self.stdout.write("  See docs/POSTGRESQL_PASSWORD_RECOVERY_WINDOWS.md")
