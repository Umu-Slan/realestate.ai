"""
Load demo users: admin, operator, reviewer, demo (readonly).
All passwords: demo123!
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.models import UserProfile, Role

User = get_user_model()

USERS = [
    ("admin", "admin@demo.local", Role.ADMIN, True),
    ("operator", "operator@demo.local", Role.OPERATOR, True),
    ("reviewer", "reviewer@demo.local", Role.REVIEWER, True),
    ("demo", "demo@demo.local", Role.DEMO, True),
]
DEFAULT_PASSWORD = "demo123!"


class Command(BaseCommand):
    help = "Load demo users with roles"

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password for all demo users")

    def handle(self, *args, **options):
        password = options["password"]
        for username, email, role, is_staff in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "is_staff": is_staff, "is_active": True},
            )
            if created:
                user.set_password(password)
                user.is_superuser = role == Role.ADMIN
                user.save()
                self.stdout.write(f"  Created: {username} ({role})")
            prof, p_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={"role": role},
            )
            if not p_created and prof.role != role:
                prof.role = role
                prof.save()
        self.stdout.write(self.style.SUCCESS("Demo users ready. Password: demo123!"))
