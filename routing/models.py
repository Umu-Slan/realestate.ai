"""
Routing decision - hot/warm/cold, CRM routing.
"""
from django.db import models

from core.models import TimestampedModel
from leads.models import Lead
from conversations.models import Conversation


class RoutingDecision(TimestampedModel):
    """
    Routing decision with reason.
    """

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="routing_decisions")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="routing_decisions", null=True, blank=True
    )
    tier = models.CharField(max_length=20)  # hot, warm, cold
    reason = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
