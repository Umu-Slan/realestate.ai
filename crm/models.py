"""
CRM records - historical lead data from external CRM.
Adapter-friendly: no vendor lock-in. Richer mapping for first company onboarding.
"""
from django.db import models

from core.models import TimestampedModel
from core.enums import SourceChannel


class CRMRecord(TimestampedModel):
    """Imported CRM record with full contact/lead mapping. Sync target for conversation outcomes."""

    crm_id = models.CharField(max_length=255, unique=True, db_index=True)
    external_phone = models.CharField(max_length=50, blank=True, db_index=True)
    external_email = models.CharField(max_length=255, blank=True, db_index=True)
    external_name = models.CharField(max_length=255, blank=True)
    external_username = models.CharField(max_length=255, blank=True, db_index=True)
    source = models.CharField(max_length=100, blank=True)
    campaign = models.CharField(max_length=255, blank=True)
    historical_classification = models.CharField(max_length=100, blank=True)
    historical_score = models.IntegerField(null=True, blank=True)
    historical_stage = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    project_interest = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=100, blank=True)
    crm_created_at = models.DateTimeField(null=True, blank=True)
    crm_updated_at = models.DateTimeField(null=True, blank=True)
    source_channel = models.CharField(
        max_length=50, choices=SourceChannel.choices, default=SourceChannel.CRM_IMPORT
    )
    raw_data = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)
    import_batch_id = models.CharField(max_length=64, blank=True, db_index=True)
    linked_customer_id = models.IntegerField(null=True, blank=True, db_index=True)

    # Richer mapping for first company / external CRM sync
    owner = models.CharField(max_length=255, blank=True, help_text="Assigned sales rep or owner")
    assigned_queue = models.CharField(max_length=100, blank=True, help_text="Queue for routing")
    lead_stage = models.CharField(max_length=100, blank=True, help_text="Current lead stage (synced)")
    tags = models.JSONField(default=list, blank=True, help_text="List of tag strings")
    support_case_id = models.IntegerField(null=True, blank=True, db_index=True)

    # Sync status for operator visibility and audit
    sync_status = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        default="internal",
        help_text="internal=local only; pending=pending external push; synced=pushed; failed=push failed",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True, help_text="Last sync failure message")
    sync_vendor = models.CharField(max_length=50, blank=True, help_text="Target vendor: salesforce, hubspot, etc.")

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self) -> str:
        return f"CRMRecord({self.crm_id})"


class CRMActivityLog(TimestampedModel):
    """Audit trail for CRM sync: notes appended, stage/owner/queue updates, support links."""

    class ActivityType(models.TextChoices):
        NOTE_ADDED = "note_added", "Note Added"
        STAGE_UPDATED = "stage_updated", "Stage Updated"
        OWNER_ASSIGNED = "owner_assigned", "Owner Assigned"
        QUEUE_ASSIGNED = "queue_assigned", "Queue Assigned"
        SUPPORT_LINKED = "support_linked", "Support Case Linked"
        TAGS_UPDATED = "tags_updated", "Tags Updated"
        RECORD_CREATED = "record_created", "Record Created"
        RECORD_UPDATED = "record_updated", "Record Updated"

    crm_record = models.ForeignKey(
        "crm.CRMRecord",
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    activity_type = models.CharField(max_length=50, choices=ActivityType.choices)
    content = models.TextField(blank=True)
    actor = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CRMActivity({self.crm_record_id}, {self.activity_type})"


class CRMMapping(TimestampedModel):
    """Company-specific field mapping for adapters. Adapter-friendly for external CRM integrations."""

    source_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="csv, excel, salesforce, hubspot, etc.",
    )
    mapping_config = models.JSONField(
        default=dict,
        help_text="External field -> internal field mapping",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["source_type"]

    def __str__(self) -> str:
        return f"CRMMapping({self.source_type})"


class CRMImportBatch(TimestampedModel):
    """Tracks CRM import batches for audit and rollback."""

    batch_id = models.CharField(max_length=64, unique=True, db_index=True)
    file_name = models.CharField(max_length=255, blank=True)
    total_rows = models.IntegerField(default=0)
    imported_count = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    conflict_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="completed")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
