"""
Company services - default company resolution, single-company behavior.
"""
from django.db import transaction

from companies.models import Company


def get_default_company() -> Company | None:
    """
    Return the default (first active) company.
    Single-company behavior: one company per deployment for v0.
    """
    return Company.objects.filter(is_active=True).order_by("id").first()


def ensure_default_company() -> Company:
    """
    Ensure at least one company exists. Create a default if none.
    Called by migration or startup.
    """
    company = get_default_company()
    if company:
        return company
    with transaction.atomic():
        company = Company.objects.create(
            name="Default Company",
            slug="default",
            support_email="support@example.com",
            tone_settings={"formality": "professional", "default_lang": "ar"},
            default_channel_settings={"enabled_channels": ["web", "whatsapp"], "default_channel": "web"},
            knowledge_namespace="",
        )
    return company
