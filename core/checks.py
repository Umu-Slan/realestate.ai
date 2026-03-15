"""
Django system checks for production readiness.
Run: python manage.py check
"""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_production_secrets(app_configs, **kwargs):
    """Warn if SECRET_KEY is default when DEBUG is False (production)."""
    errors = []
    secret = getattr(settings, "SECRET_KEY", "") or ""
    debug = getattr(settings, "DEBUG", True)
    unsafe_secrets = (
        "dev-secret-key-change-in-production",
        "change-this-in-production",
    )
    if not debug and secret in unsafe_secrets:
        errors.append(
            Warning(
                "SECRET_KEY is a known default. Set a unique SECRET_KEY in production.",
                id="core.E001",
                hint="Use: openssl rand -hex 32. Set SECRET_KEY in .env or environment.",
            )
        )
    return errors
