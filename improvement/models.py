"""
Improvement Insights - structured signals from persisted outcomes.
Reviewable by operators; no autonomous production changes.
"""
from django.db import models


# Reinforcement outcome signal types - raw events for behavior improvement
REINFORCEMENT_SIGNAL_TYPES = [
    ("user_continued_conversation", "User Continued Conversation"),
    ("user_requested_visit", "User Requested Visit"),
    ("user_asked_for_agent", "User Asked for Agent"),
    ("user_disengaged", "User Disengaged"),
    ("objection_unresolved", "Objection Unresolved"),
    ("recommendation_clicked_accepted", "Recommendation Clicked/Accepted"),
    ("support_escalation", "Support Escalation"),
    ("human_correction", "Human Correction"),
]


class ReinforcementSignal(models.Model):
    """
    Raw outcome signals for reinforcement learning / improvement.
    Links to conversation, customer, recommendation, stage, strategy.
    Feeds Improvement Insights aggregation.
    """
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reinforcement_signals",
        db_index=True,
    )
    signal_type = models.CharField(
        max_length=64,
        choices=REINFORCEMENT_SIGNAL_TYPES,
        db_index=True,
    )
    # Links
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reinforcement_signals",
        db_index=True,
    )
    customer = models.ForeignKey(
        "leads.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reinforcement_signals",
        db_index=True,
    )
    recommendation = models.ForeignKey(
        "recommendations.Recommendation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reinforcement_signals",
        db_index=True,
    )
    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reinforcement_signals",
        db_index=True,
    )
    # Context at time of signal
    journey_stage = models.CharField(max_length=64, blank=True, db_index=True)
    strategy = models.CharField(max_length=64, blank=True, db_index=True)
    intent_primary = models.CharField(max_length=64, blank=True, db_index=True)
    # Extra context (objection key, escalation reason, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["signal_type", "created_at"]),
            models.Index(fields=["journey_stage", "signal_type"]),
        ]

    def __str__(self):
        return f"ReinforcementSignal({self.signal_type}, conv={self.conversation_id})"


class ImprovementSignal(models.Model):
    """
    Aggregated improvement signal from system behavior.
    Links to source entities; recommended_action is for operator review only.
    """
    ISSUE_TYPE_CHOICES = [
        ("corrected_response", "Corrected Response"),
        ("escalation_reason", "Escalation Reason"),
        ("support_category", "Support Category"),
        ("objection_type", "Objection Type"),
        ("low_confidence", "Low Confidence"),
        ("failed_recommendation", "Failed Recommendation"),
        ("missing_qualification", "Missing Qualification Field"),
        ("score_routing_disagreement", "Score/Routing Disagreement"),
        ("reinforcement_outcome", "Reinforcement Outcome"),
        # Multi-agent sales specific
        ("repeated_fallback_reply", "Repeated Fallback Reply"),
        ("low_confidence_recommendation", "Low Confidence Recommendation"),
        ("objection_handling_failure", "Objection Handling Failure"),
        ("weak_stage_advancement", "Weak Stage Advancement"),
        ("cold_to_hot_opportunity", "Cold-to-Hot Conversion Opportunity"),
        ("high_value_escaped_late", "High-Value Lead Escalated Too Late"),
    ]
    SOURCE_FEATURE_CHOICES = [
        ("sales", "Sales"),
        ("support", "Support"),
        ("orchestration", "Orchestration"),
        ("qualification", "Qualification"),
        ("scoring", "Scoring"),
        ("recommendation", "Recommendation"),
        ("knowledge", "Knowledge"),
        ("guardrails", "Guardrails"),
    ]
    REVIEW_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("accepted", "Accepted"),
        ("dismissed", "Dismissed"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="improvement_signals",
        db_index=True,
    )
    issue_type = models.CharField(max_length=64, choices=ISSUE_TYPE_CHOICES, db_index=True)
    source_feature = models.CharField(max_length=64, choices=SOURCE_FEATURE_CHOICES, db_index=True)
    frequency = models.PositiveIntegerField(default=1)
    pattern_key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Identifier for the specific pattern (e.g. objection key, category, field name)",
    )
    affected_mode = models.CharField(max_length=64, blank=True, db_index=True)
    affected_intent = models.CharField(max_length=64, blank=True, db_index=True)
    example_refs = models.JSONField(
        default=list,
        help_text="[{type: conversation|message|correction|escalation|support_case|recommendation, id: N}]",
    )
    recommended_action = models.TextField(
        blank=True,
        help_text="Offline recommendation for operators (add FAQ, tighten guardrail, etc)",
    )
    review_status = models.CharField(
        max_length=32,
        choices=REVIEW_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    reviewed_by = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-frequency", "-last_seen_at"]
        indexes = [
            models.Index(fields=["issue_type", "review_status"]),
            models.Index(fields=["source_feature", "frequency"]),
        ]

    def __str__(self):
        return f"ImprovementSignal({self.issue_type}, {self.pattern_key}, freq={self.frequency})"
