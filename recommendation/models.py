"""
Project recommendation. Uses verified structured sources.
"""
from django.db import models

from core.models import TimestampedModel
from leads.models import Lead
from conversations.models import Conversation


class Project(models.Model):
    """
    Verified project. Exact availability and pricing from structured source.
    """

    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    property_types = models.JSONField(default=list)  # e.g. ["apartment", "villa"]
    price_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    availability_status = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Recommendation(TimestampedModel):
    """
    Recommendation given to a lead.
    """

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="recommendations")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="recommendations", null=True, blank=True
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="recommendations", null=True, blank=True
    )
    rationale = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
