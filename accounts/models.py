"""
Accounts - User and role model for v0 pilot.
Uses Django's built-in User. Role via UserProfile for admin, operator, reviewer, demo.
"""
from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    """Operator console roles."""
    ADMIN = "admin", "Admin"           # Full access, settings, users
    OPERATOR = "operator", "Operator"  # Console, corrections, support
    REVIEWER = "reviewer", "Reviewer"  # Read + approve escalations
    DEMO = "demo", "Demo"              # Read-only for stakeholders


class UserProfile(models.Model):
    """Extends User with role. One-to-one with auth.User."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_readonly(self) -> bool:
        return self.role == Role.DEMO

    @property
    def can_edit_corrections(self) -> bool:
        return self.role in (Role.ADMIN, Role.OPERATOR, Role.REVIEWER)

    @property
    def can_approve_escalations(self) -> bool:
        return self.role in (Role.ADMIN, Role.REVIEWER, Role.OPERATOR)
