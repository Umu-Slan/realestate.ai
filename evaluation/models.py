"""
Sales evaluation harness - scenarios, runs, structured scores.
"""
from django.db import models


class SalesEvalScenario(models.Model):
    """Evaluable sales scenario with expected outputs for multi-agent system."""

    class ScenarioCategory(models.TextChoices):
        INTENT = "intent", "Intent"
        QUALIFICATION = "qualification", "Qualification"
        OBJECTION = "objection", "Objection"
        RECOMMENDATION = "recommendation", "Recommendation"
        FOLLOW_UP = "follow_up", "Follow-up"
        ARABIC = "arabic", "Arabic Naturalness"
        MIXED = "mixed", "Mixed (Multi-dimension)"

    category = models.CharField(max_length=50, choices=ScenarioCategory.choices, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    # Input: conversation (last user message drives evaluation)
    messages = models.JSONField(default=list)  # [{"role": "user"|"assistant", "content": "..."}]
    # Expected outputs for scoring
    expected_intent = models.CharField(max_length=64, blank=True)
    expected_intent_aliases = models.JSONField(default=list)  # Alternative intent labels
    expected_qualification = models.JSONField(default=dict)  # {budget_min, budget_max, location, property_type}
    expected_stage = models.CharField(max_length=64, blank=True)  # awareness, consideration, shortlisting, etc.
    expected_objection_key = models.CharField(max_length=64, blank=True)  # When objection scenario
    expected_next_action = models.CharField(max_length=64, blank=True)  # ask_budget, recommend_projects, etc.
    expected_response_contains = models.JSONField(default=list)  # Substrings response must contain
    expected_response_excludes = models.JSONField(default=list)  # Substrings response must NOT contain
    # Arabic naturalness: if scenario is Arabic, we expect natural phrasing
    is_arabic_primary = models.BooleanField(default=True)
    # Recommendation relevance: when category=recommendation, expected_match_criteria
    expected_match_criteria = models.JSONField(default=dict)  # {location, budget_min, budget_max}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Sales Eval Scenario"
        verbose_name_plural = "Sales Eval Scenarios"

    def __str__(self):
        return f"{self.category}: {self.name}"


class SalesEvalRun(models.Model):
    """Single sales evaluation run with aggregate metrics."""

    run_id = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    use_llm = models.BooleanField(default=True)
    total_scenarios = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    # Structured metrics 0–1 (or count for repetition_rate)
    metrics = models.JSONField(
        default=dict,
        help_text="intent_accuracy, qualification_completeness, stage_accuracy, "
        "recommendation_relevance, objection_quality, next_step_usefulness, "
        "arabic_naturalness, repetition_rate",
    )
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sales Eval Run"
        verbose_name_plural = "Sales Eval Runs"

    def __str__(self):
        return f"SalesEvalRun {self.run_id} ({self.passed}/{self.total_scenarios})"


class SalesEvalResult(models.Model):
    """Per-scenario evaluation result with dimension scores."""

    run = models.ForeignKey(SalesEvalRun, on_delete=models.CASCADE, related_name="results")
    scenario = models.ForeignKey(SalesEvalScenario, on_delete=models.CASCADE, related_name="eval_results")
    passed = models.BooleanField(default=False)
    scores = models.JSONField(
        default=dict,
        help_text="Per-dimension scores: intent, qualification, stage, recommendation, "
        "objection, next_step, arabic_naturalness, repetition",
    )
    actual_output = models.JSONField(default=dict)
    expected_output = models.JSONField(default=dict)
    failures = models.JSONField(default=list)
    run_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run", "scenario"]
        unique_together = [("run", "scenario")]
        verbose_name = "Sales Eval Result"
        verbose_name_plural = "Sales Eval Results"

    def __str__(self):
        return f"{self.scenario.name} ({'pass' if self.passed else 'fail'})"
