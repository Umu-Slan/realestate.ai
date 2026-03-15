# Generated for v0 modular monolith

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="DemoScenario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("external_id", models.CharField(db_index=True, max_length=255)),
                ("messages", models.JSONField(default=list)),
                ("expected_intent", models.CharField(blank=True, max_length=100)),
                ("expected_temperature", models.CharField(blank=True, max_length=20)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
