"""
Lead domain: Customer, CustomerIdentity, LeadProfile, LeadQualification, LeadScore.
"""
from decimal import Decimal
from django.db import models

from core.models import TimestampedModel, AuditFieldsMixin
from core.enums import (
    CustomerType,
    LeadTemperature,
    BuyerJourneyStage,
    IntentType,
    SourceChannel,
    ConfidenceLevel,
    MergeReviewStatus,
    MemoryType,
)


class CustomerIdentity(TimestampedModel):
    """Resolved identity across channels (phone, email, external_id)."""

    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True, db_index=True)
    email = models.CharField(max_length=255, blank=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merges"
    )

    class Meta:
        verbose_name_plural = "Customer Identities"

    def __str__(self) -> str:
        return f"CustomerIdentity({self.external_id})"


class Customer(TimestampedModel, AuditFieldsMixin):
    """Customer entity - central record for lead lifecycle."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customers",
        db_index=True,
    )
    identity = models.ForeignKey(
        "CustomerIdentity",
        on_delete=models.CASCADE,
        related_name="customers",
        null=True,
        blank=True,
    )
    customer_type = models.CharField(
        max_length=50,
        choices=CustomerType.choices,
        default=CustomerType.NEW_LEAD,
    )
    source_channel = models.CharField(
        max_length=50, choices=SourceChannel.choices, default=SourceChannel.WEB
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    lifecycle_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Customer(id={self.id}, type={self.customer_type})"


class LeadProfile(TimestampedModel):
    """Lead-specific profile (one per customer/lead interaction)."""

    customer = models.ForeignKey(
        "Customer", on_delete=models.CASCADE, related_name="lead_profiles"
    )
    source_channel = models.CharField(
        max_length=50, choices=SourceChannel.choices, default=SourceChannel.WEB
    )
    project_interest = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"LeadProfile(customer={self.customer_id})"


class LeadQualification(TimestampedModel):
    """Extracted qualification data from conversation."""

    customer = models.ForeignKey(
        "Customer", on_delete=models.CASCADE, related_name="qualifications"
    )
    conversation_id = models.IntegerField(null=True, blank=True, db_index=True)
    message_id = models.IntegerField(null=True, blank=True)
    version = models.IntegerField(default=1)

    budget_min = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    budget_max = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    property_type = models.CharField(max_length=100, blank=True)
    location_preference = models.CharField(max_length=255, blank=True)
    timeline = models.CharField(max_length=100, blank=True)
    unit_size_sqm = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    raw_extraction = models.JSONField(default=dict)
    confidence = models.CharField(
        max_length=20,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.UNKNOWN,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"LeadQualification(customer={self.customer_id}, v{self.version})"


class LeadScore(TimestampedModel):
    """Computed lead score - deterministic, explainable."""

    customer = models.ForeignKey(
        "Customer", on_delete=models.CASCADE, related_name="scores"
    )
    lead_profile = models.ForeignKey(
        "LeadProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scores",
    )
    score = models.IntegerField()
    temperature = models.CharField(
        max_length=20, choices=LeadTemperature.choices
    )
    journey_stage = models.CharField(
        max_length=50,
        choices=BuyerJourneyStage.choices,
        default=BuyerJourneyStage.UNKNOWN,
    )
    next_best_action = models.CharField(max_length=255, blank=True)
    explanation = models.JSONField(default=list)
    rule_version = models.CharField(max_length=50, default="v1")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"LeadScore(customer={self.customer_id}, {self.temperature})"


class IdentityMergeCandidate(TimestampedModel):
    """Pending or processed identity merge - for manual review when confidence is low."""

    identity_a = models.ForeignKey(
        "CustomerIdentity",
        on_delete=models.CASCADE,
        related_name="merge_candidates_as_a",
    )
    identity_b = models.ForeignKey(
        "CustomerIdentity",
        on_delete=models.CASCADE,
        related_name="merge_candidates_as_b",
    )
    confidence_score = models.FloatField()
    match_reasons = models.JSONField(default=list)
    review_status = models.CharField(
        max_length=50,
        choices=MergeReviewStatus.choices,
        default=MergeReviewStatus.PENDING,
    )
    auto_approved = models.BooleanField(default=False)
    reviewed_by = models.CharField(max_length=255, blank=True)
    merged_identity_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MergeCandidate({self.identity_a_id}->{self.identity_b_id})"


class CustomerMemory(TimestampedModel):
    """Unified long-term customer memory."""

    customer = models.ForeignKey(
        "Customer",
        on_delete=models.CASCADE,
        related_name="memories",
    )
    memory_type = models.CharField(
        max_length=50,
        choices=MemoryType.choices,
    )
    content = models.TextField()
    source = models.CharField(max_length=100, blank=True)
    source_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CustomerMemory({self.customer_id}, {self.memory_type})"
