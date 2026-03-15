"""
Support: SupportCase, Escalation.
"""
from django.db import models

from core.models import TimestampedModel, AuditFieldsMixin
from core.enums import SupportCategory, SupportSeverity, SupportSLABucket, SupportStatus, EscalationReason, EscalationStatus


class SupportCase(TimestampedModel):
    """Support case - triaged from conversation."""

    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        related_name="support_cases",
        null=True,
        blank=True,
        db_index=True,
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_cases",
        db_index=True,
    )
    message_id = models.IntegerField(null=True, blank=True)
    escalation = models.ForeignKey(
        "support.Escalation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_cases",
    )
    category = models.CharField(max_length=50, choices=SupportCategory.choices)
    summary = models.TextField(blank=True)
    status = models.CharField(
        max_length=50,
        choices=SupportStatus.choices,
        default=SupportStatus.OPEN,
    )
    severity = models.CharField(
        max_length=20,
        choices=SupportSeverity.choices,
        default=SupportSeverity.MEDIUM,
        blank=True,
    )
    sla_bucket = models.CharField(
        max_length=10,
        choices=SupportSLABucket.choices,
        default=SupportSLABucket.P3,
        blank=True,
    )
    assigned_queue = models.CharField(max_length=50, blank=True)
    escalation_trigger = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SupportCase(id={self.id}, {self.category})"


class Escalation(TimestampedModel, AuditFieldsMixin):
    """Human escalation - handoff for operator review."""

    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        related_name="escalations",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalations",
    )
    reason = models.CharField(
        max_length=50, choices=EscalationReason.choices
    )
    status = models.CharField(
        max_length=50,
        choices=EscalationStatus.choices,
        default=EscalationStatus.OPEN,
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    handoff_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Escalation(id={self.id}, {self.reason})"
