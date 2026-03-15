# Generated for v0 modular monolith

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ActionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(max_length=100)),
                ("actor", models.CharField(blank=True, max_length=255)),
                ("subject_type", models.CharField(blank=True, max_length=100)),
                ("subject_id", models.CharField(blank=True, max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("reason", models.TextField(blank=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(choices=[("message_processed", "Message Processed"), ("lead_scored", "Lead Scored"), ("escalation_created", "Escalation Created"), ("escalation_resolved", "Escalation Resolved"), ("correction_applied", "Correction Applied"), ("crm_imported", "CRM Imported")], max_length=50)),
                ("actor", models.CharField(blank=True, max_length=255)),
                ("subject_type", models.CharField(blank=True, max_length=100)),
                ("subject_id", models.CharField(blank=True, max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("reason", models.TextField(blank=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="HumanCorrection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject_type", models.CharField(max_length=100)),
                ("subject_id", models.CharField(max_length=255)),
                ("field_name", models.CharField(max_length=100)),
                ("original_value", models.TextField(blank=True)),
                ("corrected_value", models.TextField()),
                ("corrected_by", models.CharField(max_length=255)),
                ("reason", models.TextField(blank=True)),
            ],
            options={"ordering": ["-id"]},
        ),
    ]
