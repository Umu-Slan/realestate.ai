"""
Admin for sales evaluation - inspectable results.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import SalesEvalScenario, SalesEvalRun, SalesEvalResult


@admin.register(SalesEvalScenario)
class SalesEvalScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "expected_intent", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at",)


@admin.register(SalesEvalRun)
class SalesEvalRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "created_at", "passed", "total_scenarios", "use_llm", "metrics_summary")
    list_filter = ("use_llm",)
    search_fields = ("run_id",)
    readonly_fields = ("run_id", "created_at", "metrics", "summary")
    date_hierarchy = "created_at"

    def metrics_summary(self, obj):
        m = obj.metrics or {}
        parts = [f"{k}: {v}" for k, v in list(m.items())[:4]]
        return ", ".join(parts) if parts else "-"

    metrics_summary.short_description = "Metrics"


@admin.register(SalesEvalResult)
class SalesEvalResultAdmin(admin.ModelAdmin):
    list_display = ("scenario", "run", "passed", "scores_summary", "run_time_ms")
    list_filter = ("passed", "run")
    search_fields = ("scenario__name",)
    readonly_fields = ("scores", "actual_output", "expected_output", "failures")
    raw_id_fields = ("run", "scenario")

    def scores_summary(self, obj):
        s = obj.scores or {}
        parts = [f"{k}={v}" for k, v in list(s.items())[:3]]
        return ", ".join(parts) if parts else "-"

    scores_summary.short_description = "Scores"
