from django.contrib import admin
from .models import ActionLog, AuditEvent, HumanCorrection


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "actor", "subject_type", "subject_id", "created_at")
    list_filter = ("action",)
    readonly_fields = ("action", "actor", "subject_type", "subject_id", "payload", "reason", "created_at", "updated_at")
    search_fields = ("actor", "subject_id")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "actor", "subject_type", "subject_id", "created_at")
    list_filter = ("action",)
    readonly_fields = ("action", "actor", "subject_type", "subject_id", "payload", "reason", "created_at", "updated_at")


@admin.register(HumanCorrection)
class HumanCorrectionAdmin(admin.ModelAdmin):
    list_display = ("id", "subject_type", "subject_id", "field_name", "corrected_by", "created_at")
    list_filter = ("subject_type",)
    search_fields = ("subject_id", "corrected_by")
