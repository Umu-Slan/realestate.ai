# Initial onboarding models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("companies", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch_type", models.CharField(choices=[("documents", "Documents"), ("structured", "Structured Data"), ("crm", "CRM Export")], max_length=50)),
                ("name", models.CharField(blank=True, help_text="Optional label (e.g. 'Initial docs Q1 2025')", max_length=255)),
                ("status", models.CharField(default="in_progress", help_text="in_progress | completed | partial", max_length=50)),
                ("imported_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("stale_count", models.PositiveIntegerField(default=0)),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("created_by", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="onboarding_batches", to="companies.company")),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name_plural": "Onboarding batches",
            },
        ),
        migrations.CreateModel(
            name="OnboardingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("item_type", models.CharField(help_text="document | structured_row | crm_row", max_length=50)),
                ("source_name", models.CharField(help_text="File name or row identifier", max_length=500)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Imported"), ("skipped", "Skipped"), ("failed", "Failed"), ("stale", "Stale")], default="pending", max_length=50)),
                ("error_message", models.TextField(blank=True)),
                ("document_id", models.IntegerField(blank=True, null=True)),
                ("project_id", models.IntegerField(blank=True, null=True)),
                ("crm_record_id", models.IntegerField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="onboarding.onboardingbatch")),
            ],
            options={
                "ordering": ["batch", "id"],
            },
        ),
    ]
