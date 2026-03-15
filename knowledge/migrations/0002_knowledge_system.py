# Knowledge system: RawDocument, IngestedDocument, DocumentVersion, DocumentChunk

import pgvector.django
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("knowledge", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="last_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="RawDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file_path", models.CharField(max_length=1000)),
                ("file_name", models.CharField(max_length=255)),
                ("file_hash", models.CharField(db_index=True, max_length=64)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("document_type", models.CharField(choices=[("project_pdf", "Project PDF"), ("case_study", "Case Study"), ("achievement", "Achievement"), ("delivery_history", "Delivery History"), ("faq", "FAQ"), ("support_sop", "Support SOP"), ("objection_handling", "Objection Handling"), ("project_metadata_csv", "Project Metadata CSV"), ("credibility", "Credibility"), ("other", "Other")], default="other", max_length=50)),
                ("source_name", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by", models.CharField(blank=True, max_length=255)),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="IngestedDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.CharField(blank=True, max_length=255)),
                ("updated_by", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("document_type", models.CharField(choices=[("project_pdf", "Project PDF"), ("case_study", "Case Study"), ("achievement", "Achievement"), ("delivery_history", "Delivery History"), ("faq", "FAQ"), ("support_sop", "Support SOP"), ("objection_handling", "Objection Handling"), ("project_metadata_csv", "Project Metadata CSV"), ("credibility", "Credibility"), ("other", "Other")], max_length=50)),
                ("source_name", models.CharField(max_length=255)),
                ("title", models.CharField(max_length=500)),
                ("source_of_truth", models.BooleanField(default=False)),
                ("uploaded_at", models.DateTimeField()),
                ("parsed_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.IntegerField(default=1)),
                ("language", models.CharField(choices=[("ar", "Arabic"), ("en", "English"), ("ar_en", "Arabic & English"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("verification_status", models.CharField(choices=[("unverified", "Unverified"), ("pending", "Pending"), ("verified", "Verified"), ("stale", "Stale"), ("superseded", "Superseded")], default="unverified", max_length=50)),
                ("validity_window_start", models.DateField(blank=True, null=True)),
                ("validity_window_end", models.DateField(blank=True, null=True)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("parsed_content", models.TextField(blank=True)),
                ("status", models.CharField(default="pending", max_length=50)),
                ("error_message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ingested_documents", to="knowledge.project")),
                ("raw_document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ingested_versions", to="knowledge.rawdocument")),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="DocumentVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version_number", models.IntegerField()),
                ("parsed_content", models.TextField()),
                ("snapshot_metadata", models.JSONField(default=dict)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="knowledge.ingesteddocument")),
            ],
            options={"ordering": ["document", "-version_number"], "unique_together": {("document", "version_number")}},
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_index", models.IntegerField()),
                ("chunk_type", models.CharField(choices=[("project_section", "Project Section"), ("payment_plan", "Payment Plan"), ("amenities", "Amenities"), ("location", "Location"), ("company_achievement", "Company Achievement"), ("delivery_proof", "Delivery Proof"), ("faq_topic", "FAQ Topic"), ("objection_topic", "Objection Topic"), ("support_procedure", "Support Procedure"), ("general", "General")], default="general", max_length=50)),
                ("section_title", models.CharField(blank=True, max_length=500)),
                ("content", models.TextField()),
                ("language", models.CharField(choices=[("ar", "Arabic"), ("en", "English"), ("ar_en", "Arabic & English"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("embedding", pgvector.django.VectorField(blank=True, dimensions=1536, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="knowledge.ingesteddocument")),
            ],
            options={"ordering": ["document", "chunk_index"], "unique_together": {("document", "chunk_index")}},
        ),
    ]
