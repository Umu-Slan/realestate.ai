# CRM integration foundation: richer mapping, activity log, sync support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("crm", "0002_crm_extended")]

    operations = [
        migrations.AddField(
            model_name="crmrecord",
            name="owner",
            field=models.CharField(blank=True, help_text="Assigned sales rep or owner", max_length=255),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="assigned_queue",
            field=models.CharField(blank=True, help_text="Queue for routing", max_length=100),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="lead_stage",
            field=models.CharField(blank=True, help_text="Current lead stage (synced)", max_length=100),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="tags",
            field=models.JSONField(blank=True, default=list, help_text="List of tag strings"),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="support_case_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name="CRMActivityLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity_type", models.CharField(choices=[("note_added", "Note Added"), ("stage_updated", "Stage Updated"), ("owner_assigned", "Owner Assigned"), ("queue_assigned", "Queue Assigned"), ("support_linked", "Support Case Linked"), ("tags_updated", "Tags Updated"), ("record_created", "Record Created"), ("record_updated", "Record Updated")], max_length=50)),
                ("content", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("crm_record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_logs", to="crm.crmrecord")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CRMMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_type", models.CharField(db_index=True, help_text="csv, excel, salesforce, hubspot, etc.", max_length=50)),
                ("mapping_config", models.JSONField(default=dict, help_text="External field -> internal field mapping")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["source_type"]},
        ),
    ]
