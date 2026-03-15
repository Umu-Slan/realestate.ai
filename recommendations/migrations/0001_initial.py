# Generated for v0 modular monolith

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("conversations", "0001_initial"),
        ("knowledge", "0001_initial"),
        ("leads", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Recommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rationale", models.TextField(blank=True)),
                ("rank", models.IntegerField(default=1)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recommendations", to="conversations.conversation")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendations", to="leads.customer")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendations", to="knowledge.project")),
            ],
            options={"ordering": ["customer", "rank"]},
        ),
    ]
