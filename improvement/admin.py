from django.contrib import admin
from .models import ImprovementSignal, ReinforcementSignal


@admin.register(ReinforcementSignal)
class ReinforcementSignalAdmin(admin.ModelAdmin):
    list_display = ("signal_type", "conversation_id", "customer_id", "journey_stage", "strategy", "created_at")
    list_filter = ("signal_type", "journey_stage")
    search_fields = ("signal_type", "strategy")
    readonly_fields = ("created_at",)
    ordering = ["-created_at"]


@admin.register(ImprovementSignal)
class ImprovementSignalAdmin(admin.ModelAdmin):
    list_display = ("issue_type", "pattern_key", "frequency", "source_feature", "review_status", "last_seen_at")
    list_filter = ("issue_type", "source_feature", "review_status")
    search_fields = ("pattern_key", "recommended_action")
    readonly_fields = ("frequency", "last_seen_at", "created_at")
    ordering = ["-frequency", "-last_seen_at"]
