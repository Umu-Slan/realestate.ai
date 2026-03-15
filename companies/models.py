"""
Company configuration - first company onboarding, future multi-company ready.
Single-company by default; architecture allows expansion without major redesign.
"""
from django.db import models

from core.models import TimestampedModel


class Company(TimestampedModel):
    """
    Company/organization configuration.
    Links customers, projects, knowledge. Single-company default for v0.
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    # Branding basics
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=20, blank=True, help_text="Hex e.g. #1a365d")
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=50, blank=True)
    website_url = models.URLField(blank=True)

    # Contact details (can extend via metadata)
    contact_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra contact info: address, social links, etc.",
    )

    # Tone/policy settings - influences responses
    tone_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="formality, default_lang, escalation_preferences, etc.",
    )

    # Default channel settings
    default_channel_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="enabled_channels, default_channel, channel_config per channel",
    )

    # Knowledge namespace - for future partitioning/isolation
    knowledge_namespace = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Namespace for knowledge partitioning; blank = default",
    )

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
