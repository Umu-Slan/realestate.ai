# IdentityMergeCandidate, CustomerMemory

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("leads", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="IdentityMergeCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confidence_score", models.FloatField()),
                ("match_reasons", models.JSONField(default=list)),
                ("review_status", models.CharField(choices=[("pending", "Pending"), ("auto_approved", "Auto Approved"), ("manual_approved", "Manual Approved"), ("rejected", "Rejected")], default="pending", max_length=50)),
                ("auto_approved", models.BooleanField(default=False)),
                ("reviewed_by", models.CharField(blank=True, max_length=255)),
                ("merged_identity_id", models.IntegerField(blank=True, null=True)),
                ("identity_a", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="merge_candidates_as_a", to="leads.customeridentity")),
                ("identity_b", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="merge_candidates_as_b", to="leads.customeridentity")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CustomerMemory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("memory_type", models.CharField(choices=[("preference", "Preference"), ("past_intent", "Past Intent"), ("past_project", "Past Project"), ("old_objection", "Old Objection"), ("prior_classification", "Prior Classification"), ("support_history", "Support History")], max_length=50)),
                ("content", models.TextField()),
                ("source", models.CharField(blank=True, max_length=100)),
                ("source_id", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memories", to="leads.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
