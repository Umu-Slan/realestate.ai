# Generated manually for ReinforcementSignal model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("improvement", "0001_initial"),
        ("companies", "0001_initial"),
        ("conversations", "0001_initial"),
        ("leads", "0001_initial"),
        ("recommendations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReinforcementSignal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("signal_type", models.CharField(
                    choices=[
                        ("user_continued_conversation", "User Continued Conversation"),
                        ("user_requested_visit", "User Requested Visit"),
                        ("user_asked_for_agent", "User Asked for Agent"),
                        ("user_disengaged", "User Disengaged"),
                        ("objection_unresolved", "Objection Unresolved"),
                        ("recommendation_clicked_accepted", "Recommendation Clicked/Accepted"),
                        ("support_escalation", "Support Escalation"),
                        ("human_correction", "Human Correction"),
                    ],
                    db_index=True,
                    max_length=64,
                )),
                ("journey_stage", models.CharField(blank=True, db_index=True, max_length=64)),
                ("strategy", models.CharField(blank=True, db_index=True, max_length=64)),
                ("intent_primary", models.CharField(blank=True, db_index=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reinforcement_signals",
                        to="companies.company",
                    ),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reinforcement_signals",
                        to="conversations.conversation",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reinforcement_signals",
                        to="leads.customer",
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reinforcement_signals",
                        to="conversations.message",
                    ),
                ),
                (
                    "recommendation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        db_index=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reinforcement_signals",
                        to="recommendations.recommendation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="reinforcementsignal",
            index=models.Index(fields=["signal_type", "created_at"], name="impr_signal_created_idx"),
        ),
        migrations.AddIndex(
            model_name="reinforcementsignal",
            index=models.Index(fields=["journey_stage", "signal_type"], name="impr_stage_signal_idx"),
        ),
    ]
