# Generated for v0 modular monolith

import pgvector.django
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [("core", "0001_initial")]

    operations = [
        pgvector.django.VectorExtension(),
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("name_ar", models.CharField(blank=True, max_length=255)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("property_types", models.JSONField(default=list)),
                ("price_min", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("price_max", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("availability_status", models.CharField(blank=True, max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="ProjectDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=500)),
                ("source_type", models.CharField(choices=[("project", "Project"), ("case_study", "Case Study"), ("achievement", "Achievement"), ("credibility", "Credibility"), ("delivery", "Delivery"), ("other", "Other")], max_length=50)),
                ("file_path", models.CharField(max_length=1000)),
                ("file_hash", models.CharField(blank=True, db_index=True, max_length=64)),
                ("status", models.CharField(default="pending", max_length=50)),
                ("error_message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents", to="knowledge.project")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_index", models.IntegerField()),
                ("content", models.TextField()),
                ("embedding", pgvector.django.VectorField(blank=True, dimensions=1536, null=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="knowledge.projectdocument")),
            ],
            options={"ordering": ["document", "chunk_index"], "unique_together": {("document", "chunk_index")}},
        ),
    ]
