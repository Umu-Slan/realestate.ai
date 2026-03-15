from django.contrib import admin
from .models import DemoScenario, DemoEvalRun, DemoEvalResult


@admin.register(DemoScenario)
class DemoScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "scenario_type", "expected_intent", "expected_temperature", "expected_route")
    list_filter = ("scenario_type",)
    search_fields = ("name", "description")


@admin.register(DemoEvalRun)
class DemoEvalRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "created_at", "passed", "total_scenarios", "use_llm")


@admin.register(DemoEvalResult)
class DemoEvalResultAdmin(admin.ModelAdmin):
    list_display = ("run", "scenario", "passed", "run_time_ms")
    list_filter = ("passed",)
