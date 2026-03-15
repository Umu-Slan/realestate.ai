"""
Conversation and Message models.
"""
from django.db import models

from core.models import TimestampedModel
from core.enums import ConversationStatus, IntentType, SourceChannel, ConfidenceLevel


class Conversation(TimestampedModel):
    """Unified conversation - one per customer/channel session."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conversations",
        db_index=True,
    )
    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    channel = models.CharField(
        max_length=50, choices=SourceChannel.choices, default=SourceChannel.WEB
    )
    status = models.CharField(
        max_length=50,
        choices=ConversationStatus.choices,
        default=ConversationStatus.ACTIVE,
    )
    metadata = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Conversation(id={self.id}, customer={self.customer_id})"




class Message(TimestampedModel):
    """Single message in a conversation."""

    conversation = models.ForeignKey(
        "Conversation", on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20)
    content = models.TextField()
    language = models.CharField(max_length=10, blank=True)
    intent = models.CharField(
        max_length=50,
        choices=IntentType.choices,
        blank=True,
    )
    intent_confidence = models.CharField(
        max_length=20,
        choices=ConfidenceLevel.choices,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message(id={self.id}, {self.role})"
