"""
Audit: ActionLog, AuditEvent.
"""
from django.db import models

from core.models import TimestampedModel
from core.enums import AuditAction


class ActionLog(TimestampedModel):
    """Immutable action log for audit trail."""

    action = models.CharField(max_length=100)
    actor = models.CharField(max_length=255, blank=True)
    subject_type = models.CharField(max_length=100, blank=True)
    subject_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ActionLog({self.action}, {self.subject_type})"


class AuditEvent(TimestampedModel):
    """Structured audit event with action enum."""

    action = models.CharField(
        max_length=50, choices=AuditAction.choices
    )
    actor = models.CharField(max_length=255, blank=True)
    subject_type = models.CharField(max_length=100, blank=True)
    subject_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AuditEvent({self.get_action_display()})"


class HumanCorrection(TimestampedModel):
    """
    Human correction for ML/rule output - supports human-in-the-loop.
    When linked to message, stores conversation/customer/mode for tuning.
    sales_linkage stores strategy, objection_type, recommendation_quality, stage_decision.
    """

    subject_type = models.CharField(max_length=100)
    subject_id = models.CharField(max_length=255)
    field_name = models.CharField(max_length=100)
    original_value = models.TextField(blank=True)
    corrected_value = models.TextField()
    corrected_by = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    # Linkage for response corrections
    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="human_corrections",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="human_corrections",
    )
    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="human_corrections",
    )
    mode = models.CharField(max_length=50, blank=True)
    issue_type = models.CharField(max_length=50, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)  # True=marked good, False=correction
    # Sales linkage for improvement insights: {strategy, objection_type, recommendation_quality, stage_decision}
    sales_linkage = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"HumanCorrection({self.subject_type}:{self.subject_id})"
