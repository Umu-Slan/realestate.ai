"""
Escalation workflow.
"""
from django.db import models

from core.models import TimestampedModel, AuditFieldsMixin
from leads.models import Lead
from conversations.models import Conversation


class Escalation(TimestampedModel, AuditFieldsMixin):
    """
    Escalation record. Human handoff.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("cancelled", "Cancelled"),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="escalations")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="escalations", null=True, blank=True
    )
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="open")
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
