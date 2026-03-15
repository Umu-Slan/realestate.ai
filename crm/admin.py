from django.contrib import admin
from .models import CRMRecord, CRMImportBatch, CRMActivityLog, CRMMapping


class CRMActivityLogInline(admin.TabularInline):
    model = CRMActivityLog
    extra = 0
    readonly_fields = ("activity_type", "content", "actor", "created_at")


@admin.register(CRMRecord)
class CRMRecordAdmin(admin.ModelAdmin):
    list_display = ("crm_id", "external_name", "external_phone", "owner", "lead_stage", "historical_classification", "linked_customer_id")
    list_filter = ("source_channel", "lead_stage")
    search_fields = ("crm_id", "external_phone", "external_email", "external_name", "owner")
    readonly_fields = ("imported_at",)
    inlines = [CRMActivityLogInline]


@admin.register(CRMMapping)
class CRMMappingAdmin(admin.ModelAdmin):
    list_display = ("source_type", "is_active")
    list_filter = ("is_active",)


@admin.register(CRMActivityLog)
class CRMActivityLogAdmin(admin.ModelAdmin):
    list_display = ("crm_record", "activity_type", "actor", "created_at")
    list_filter = ("activity_type",)


@admin.register(CRMImportBatch)
class CRMImportBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_id", "file_name", "total_rows", "imported_count", "duplicate_count", "conflict_count", "error_count", "status")
