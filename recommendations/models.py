"""
Recommendation - project recommendations for leads.
"""
from django.db import models

from core.models import TimestampedModel


class Recommendation(TimestampedModel):
    """Recommendation given to a lead."""

    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    project = models.ForeignKey(
        "knowledge.Project",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    rationale = models.TextField(blank=True)
    rank = models.IntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["customer", "rank"]

    def __str__(self) -> str:
        return f"Recommendation(customer={self.customer_id}, project={self.project_id})"
