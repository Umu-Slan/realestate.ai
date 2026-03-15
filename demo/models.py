"""
Demo scenarios and evaluation results for v0 pilot.
"""
from django.db import models


class DemoScenario(models.Model):
    """Evaluable demo scenario with expected outputs."""

    class ScenarioType(models.TextChoices):
        NEW_LEAD = "new_lead", "New Lead"
        HOT_LEAD = "hot_lead", "Hot Lead"
        WARM_LEAD = "warm_lead", "Warm Lead"
        COLD_LEAD = "cold_lead", "Cold Lead"
        SUPPORT_CASE = "support_case", "Support Case"
        ANGRY_CUSTOMER = "angry_customer", "Angry Customer"
        LEGAL_CASE = "legal_case", "Legal/Contract"
        SPAM = "spam", "Spam/Fake"
        BROKER = "broker", "Broker/Partner"
        AMBIGUOUS_IDENTITY = "ambiguous_identity", "Ambiguous Identity"

    scenario_type = models.CharField(max_length=50, choices=ScenarioType.choices, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # Input: last user message drives evaluation (conversation_history optional)
    messages = models.JSONField(default=list)  # [{"role": "user"|"assistant", "content": "..."}]
    # Expected outputs for comparison
    expected_customer_type = models.CharField(max_length=50, blank=True)
    expected_intent = models.CharField(max_length=50, blank=True)
    expected_temperature = models.CharField(max_length=20, blank=True)  # hot, warm, cold, nurture
    expected_support_category = models.CharField(max_length=50, blank=True)
    expected_route = models.CharField(max_length=50, blank=True)
    expected_escalation = models.BooleanField(default=False)
    expected_next_action = models.CharField(max_length=100, blank=True)
    expected_qualification_hints = models.JSONField(default=dict)  # {budget_min, location, etc.}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scenario_type", "name"]

    def __str__(self):
        return f"{self.scenario_type}: {self.name}"


class DemoEvalRun(models.Model):
    """Single evaluation run - stores results for reporting."""

    run_id = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    use_llm = models.BooleanField(default=True)
    total_scenarios = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    metrics = models.JSONField(default=dict)  # intent_accuracy, temp_agreement, etc.
    summary = models.TextField(blank=True)


class DemoEvalResult(models.Model):
    """Per-scenario evaluation result."""

    run = models.ForeignKey(DemoEvalRun, on_delete=models.CASCADE, related_name="results")
    scenario = models.ForeignKey(DemoScenario, on_delete=models.CASCADE, related_name="eval_results")
    passed = models.BooleanField(default=False)
    actual_output = models.JSONField(default=dict)  # intent, routing, scoring, etc.
    expected_output = models.JSONField(default=dict)
    failures = models.JSONField(default=list)  # ["intent mismatch", "temperature mismatch"]
    run_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run", "scenario"]
        unique_together = [("run", "scenario")]
