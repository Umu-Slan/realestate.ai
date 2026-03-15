# Generated manually for improvement app

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("companies", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="ImprovementSignal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_type", models.CharField(
                    choices=[
                        ("corrected_response", "Corrected Response"),
                        ("escalation_reason", "Escalation Reason"),
                        ("support_category", "Support Category"),
                        ("objection_type", "Objection Type"),
                        ("low_confidence", "Low Confidence"),
                        ("failed_recommendation", "Failed Recommendation"),
                        ("missing_qualification", "Missing Qualification Field"),
                        ("score_routing_disagreement", "Score/Routing Disagreement"),
                    ],
                    db_index=True,
                    max_length=64,
                )),
                ("source_feature", models.CharField(
                    choices=[
                        ("sales", "Sales"),
                        ("support", "Support"),
                        ("orchestration", "Orchestration"),
                        ("qualification", "Qualification"),
                        ("scoring", "Scoring"),
                        ("recommendation", "Recommendation"),
                        ("knowledge", "Knowledge"),
                        ("guardrails", "Guardrails"),
                    ],
                    db_index=True,
                    max_length=64,
                )),
                ("frequency", models.PositiveIntegerField(default=1)),
                ("pattern_key", models.CharField(db_index=True, help_text="Identifier for the specific pattern", max_length=255)),
                ("affected_mode", models.CharField(blank=True, db_index=True, max_length=64)),
                ("affected_intent", models.CharField(blank=True, db_index=True, max_length=64)),
                ("example_refs", models.JSONField(
                    default=list,
                    help_text="[{type: conversation|message|correction|escalation|support_case|recommendation, id: N}]",
                )),
                ("recommended_action", models.TextField(
                    blank=True,
                    help_text="Offline recommendation for operators",
                )),
                ("review_status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("reviewed", "Reviewed"),
                        ("accepted", "Accepted"),
                        ("dismissed", "Dismissed"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=32,
                )),
                ("reviewed_by", models.CharField(blank=True, max_length=255)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="improvement_signals",
                        to="companies.company",
                    ),
                ),
            ],
            options={
                "ordering": ["-frequency", "-last_seen_at"],
            },
        ),
        migrations.AddIndex(
            model_name="improvementsignal",
            index=models.Index(fields=["issue_type", "review_status"], name="impr_issue_rev_idx"),
        ),
        migrations.AddIndex(
            model_name="improvementsignal",
            index=models.Index(fields=["source_feature", "frequency"], name="impr_src_freq_idx"),
        ),
    ]
