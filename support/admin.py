from django.contrib import admin
from .models import SupportCase, Escalation


@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "category", "status", "severity", "assigned_queue")
    list_filter = ("category", "status")
    search_fields = ("summary",)


@admin.register(Escalation)
class EscalationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "reason", "status", "created_at")
    list_filter = ("reason", "status")
    raw_id_fields = ("customer", "conversation")
    readonly_fields = ("resolved_at",)
