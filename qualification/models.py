"""
Lead qualification extraction - stored per conversation/lead.
"""
from django.db import models

from core.models import TimestampedModel
from leads.models import Lead
from conversations.models import Conversation


class LeadQualification(TimestampedModel):
    """
    Extracted qualification data. Versioned per extraction.
    """

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="qualifications")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="qualifications", null=True, blank=True
    )
    message_id = models.IntegerField(null=True, blank=True)
    version = models.IntegerField(default=1)

    # Extracted fields
    budget_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    property_type = models.CharField(max_length=100, blank=True)
    location_preference = models.CharField(max_length=255, blank=True)
    timeline = models.CharField(max_length=100, blank=True)
    raw_extraction = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
