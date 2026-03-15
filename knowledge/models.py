"""
Knowledge: Project, RawDocument, IngestedDocument, DocumentVersion, KnowledgeChunk.
Hybrid knowledge layer for Egyptian real estate.
"""
from django.db import models
from pgvector.django import VectorField

from core.models import TimestampedModel, AuditFieldsMixin
from core.enums import (
    DocumentType,
    VerificationStatus,
    ChunkType,
    ContentLanguage,
    AccessLevel,
    FactSource,
)


class Project(TimestampedModel):
    """Verified project - structured source for pricing/availability. Source of truth."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="projects",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    property_types = models.JSONField(default=list)
    price_min = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    price_max = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    availability_status = models.CharField(max_length=50, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    pricing_source = models.CharField(
        max_length=20,
        choices=FactSource.choices,
        default=FactSource.MANUAL,
        blank=True,
    )
    availability_source = models.CharField(
        max_length=20,
        choices=FactSource.choices,
        default=FactSource.MANUAL,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProjectPaymentPlan(TimestampedModel):
    """Structured payment plan facts. One per project (or per phase if needed)."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="payment_plans",
    )
    down_payment_pct_min = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Min down payment percentage (e.g. 10)",
    )
    down_payment_pct_max = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    installment_years_min = models.PositiveSmallIntegerField(null=True, blank=True)
    installment_years_max = models.PositiveSmallIntegerField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=20,
        choices=FactSource.choices,
        default=FactSource.MANUAL,
    )
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["project"]

    def __str__(self) -> str:
        return f"PaymentPlan({self.project.name})"


class ProjectDeliveryTimeline(TimestampedModel):
    """Structured delivery timeline. Multiple phases per project."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="delivery_timelines",
    )
    phase_name = models.CharField(max_length=255)
    phase_name_ar = models.CharField(max_length=255, blank=True)
    expected_start_date = models.DateField(null=True, blank=True)
    expected_end_date = models.DateField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=20,
        choices=FactSource.choices,
        default=FactSource.MANUAL,
    )
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["project", "expected_start_date"]

    def __str__(self) -> str:
        return f"Delivery({self.project.name}: {self.phase_name})"


class ProjectUnitCategory(TimestampedModel):
    """Unit category with price range and optional inventory."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="unit_categories",
    )
    category_name = models.CharField(max_length=255)
    category_name_ar = models.CharField(max_length=255, blank=True)
    price_min = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    price_max = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    quantity_available = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Optional. For ERP/inventory sync.",
    )
    last_verified_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=20,
        choices=FactSource.choices,
        default=FactSource.MANUAL,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["project", "category_name"]
        verbose_name_plural = "Project unit categories"

    def __str__(self) -> str:
        return f"{self.project.name}: {self.category_name}"


class RawDocument(TimestampedModel):
    """Uploaded raw file - before parsing."""

    file_path = models.CharField(max_length=1000)
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    document_type = models.CharField(
        max_length=50, choices=DocumentType.choices, default=DocumentType.OTHER
    )
    source_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"RawDocument({self.file_name})"


class IngestedDocument(TimestampedModel, AuditFieldsMixin):
    """
    Parsed document with full tracking. After parsing from RawDocument or direct import.
    """

    raw_document = models.ForeignKey(
        RawDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingested_versions",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ingested_documents",
        db_index=True,
        help_text="Company for company-level docs (SOPs, credibility); project inherits from company if set.",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingested_documents",
    )
    document_type = models.CharField(
        max_length=50, choices=DocumentType.choices
    )
    source_name = models.CharField(max_length=255)
    title = models.CharField(max_length=500)
    source_of_truth = models.BooleanField(
        default=False,
        help_text="If True, this doc is authoritative for its domain",
    )
    uploaded_at = models.DateTimeField()
    parsed_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)
    language = models.CharField(
        max_length=20,
        choices=ContentLanguage.choices,
        default=ContentLanguage.UNKNOWN,
    )
    verification_status = models.CharField(
        max_length=50,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    validity_window_start = models.DateField(null=True, blank=True)
    validity_window_end = models.DateField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.INTERNAL,
        help_text="Public=general use; Internal=staff; Restricted=sensitive",
    )
    parsed_content = models.TextField(blank=True)
    status = models.CharField(
        max_length=50, default="pending"
    )  # pending, parsed, chunked, embedded, failed
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"IngestedDocument({self.title[:50]})"


class DocumentVersion(TimestampedModel):
    """Version history for ingested documents."""

    document = models.ForeignKey(
        IngestedDocument,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.IntegerField()
    parsed_content = models.TextField()
    snapshot_metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = [("document", "version_number")]
        ordering = ["document", "-version_number"]

    def __str__(self) -> str:
        return f"DocVersion(doc={self.document_id}, v{self.version_number})"


class DocumentChunk(TimestampedModel):
    """
    Vectorized chunk with business-aware typing.
    Links to IngestedDocument.
    """

    document = models.ForeignKey(
        IngestedDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.IntegerField()
    chunk_type = models.CharField(
        max_length=50,
        choices=ChunkType.choices,
        default=ChunkType.GENERAL,
    )
    section_title = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    language = models.CharField(
        max_length=20,
        choices=ContentLanguage.choices,
        default=ContentLanguage.UNKNOWN,
    )
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("document", "chunk_index")]
        ordering = ["document", "chunk_index"]

    def __str__(self) -> str:
        return f"DocumentChunk(doc={self.document_id}, {self.chunk_type}, idx={self.chunk_index})"


class ProjectDocument(TimestampedModel):
    """Legacy document linked to project. Prefer IngestedDocument for new ingestion."""

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_documents",
    )
    title = models.CharField(max_length=500)
    source_type = models.CharField(max_length=50, default="project")
    file_path = models.CharField(max_length=1000)
    file_hash = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=50, default="pending")
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
