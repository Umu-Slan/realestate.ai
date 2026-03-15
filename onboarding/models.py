"""
Onboarding models: batches and items for real-data ingestion.
Tracks document uploads, structured imports, CRM imports with clear status.
"""
from django.db import models

from core.models import TimestampedModel


class OnboardingBatchType(models.TextChoices):
    """Type of onboarding run."""
    DOCUMENTS = "documents", "Documents"
    STRUCTURED = "structured", "Structured Data"
    CRM = "crm", "CRM Export"


class OnboardingItemStatus(models.TextChoices):
    """Status of an individual onboarding item."""
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Imported"
    SKIPPED = "skipped", "Skipped"
    FAILED = "failed", "Failed"
    STALE = "stale", "Stale"


class OnboardingBatch(TimestampedModel):
    """
    Tracks a single onboarding run. Reusable for any company.
    Source of truth for import summaries: imported, skipped, failed, stale.
    """
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="onboarding_batches",
        db_index=True,
    )
    batch_type = models.CharField(
        max_length=50,
        choices=OnboardingBatchType.choices,
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label (e.g. 'Initial docs Q1 2025')",
    )
    status = models.CharField(
        max_length=50,
        default="in_progress",
        help_text="in_progress | completed | partial",
    )
    imported_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    stale_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    created_by = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Onboarding batches"

    def __str__(self) -> str:
        return f"Batch({self.batch_type}, {self.id})"

    @property
    def summary(self) -> dict:
        return {
            "imported": self.imported_count,
            "skipped": self.skipped_count,
            "failed": self.failed_count,
            "stale": self.stale_count,
            "total": self.total_count,
        }


class OnboardingItem(TimestampedModel):
    """
    Single item in an onboarding batch. Links to created document/project/crm batch.
    """
    batch = models.ForeignKey(
        OnboardingBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(
        max_length=50,
        help_text="document | structured_row | crm_row",
    )
    source_name = models.CharField(max_length=500, help_text="File name or row identifier")
    status = models.CharField(
        max_length=50,
        choices=OnboardingItemStatus.choices,
        default=OnboardingItemStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    document_id = models.IntegerField(null=True, blank=True)
    project_id = models.IntegerField(null=True, blank=True)
    crm_record_id = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["batch", "id"]

    def __str__(self) -> str:
        return f"Item({self.batch_id}, {self.source_name[:30]})"
