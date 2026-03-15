"""
Core base models and mixins.
"""
from django.db import models


class TimestampedModel(models.Model):
    """Mixin for created_at, updated_at."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditFieldsMixin(models.Model):
    """Mixin for audit metadata (who, why)."""

    created_by = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True
