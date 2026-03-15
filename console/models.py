"""
Console models - persist orchestration snapshot per message for inspectability.
"""
from django.db import models


class OrchestrationSnapshot(models.Model):
    """Stored orchestration run output for a message - for operator inspection."""

    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="orchestration_snapshots",
    )
    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.CASCADE,
        related_name="orchestration_snapshots",
        null=True,
        blank=True,
    )
    run_id = models.CharField(max_length=64, db_index=True)
    # Stage outputs as JSON
    intent = models.JSONField(default=dict)
    qualification = models.JSONField(default=dict)
    scoring = models.JSONField(default=dict)
    routing = models.JSONField(default=dict)
    retrieval_sources = models.JSONField(default=list)
    policy_decision = models.JSONField(default=dict)
    actions_triggered = models.JSONField(default=list)
    next_best_action = models.CharField(max_length=255, blank=True)
    response_produced = models.TextField(blank=True)
    customer_type = models.CharField(max_length=50, blank=True)
    mode = models.CharField(max_length=50, blank=True)
    source_channel = models.CharField(max_length=50, blank=True)
    escalation_flag = models.BooleanField(default=False)
    journey_stage = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OrchestrationSnapshot(run={self.run_id})"


class ResponseFeedback(models.Model):
    """
    Operator/reviewer feedback on AI response - human-in-the-loop.
    Linked to conversation, message, customer, mode for prompt/rule tuning.
    Supports 3-way quality (good/weak/wrong) and sales linkage for improvement insights.
    """

    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="response_feedback",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        related_name="response_feedback",
        null=True,
        blank=True,
    )
    mode = models.CharField(max_length=50, blank=True)  # For tuning by mode
    is_good = models.BooleanField(default=False)  # Legacy: True when quality=good
    # 3-way quality: good / weak / wrong
    quality = models.CharField(max_length=20, blank=True, db_index=True)
    corrected_response = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    category = models.CharField(max_length=50, blank=True)  # Legacy
    issue_type = models.CharField(max_length=50, blank=True)  # CorrectionIssueType
    # Sales linkage for improvement insights
    strategy = models.CharField(max_length=64, blank=True, db_index=True)
    objection_type = models.CharField(max_length=64, blank=True, db_index=True)
    recommendation_quality = models.CharField(max_length=64, blank=True, db_index=True)
    stage_decision = models.CharField(max_length=64, blank=True, db_index=True)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback(msg={self.message_id}, quality={self.quality or ('good' if self.is_good else 'corrected')})"
