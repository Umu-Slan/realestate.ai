# Generated for v0 modular monolith

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CRMRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("crm_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("external_phone", models.CharField(blank=True, db_index=True, max_length=50)),
                ("external_email", models.CharField(blank=True, db_index=True, max_length=255)),
                ("external_name", models.CharField(blank=True, max_length=255)),
                ("historical_classification", models.CharField(blank=True, max_length=100)),
                ("historical_score", models.IntegerField(blank=True, null=True)),
                ("historical_stage", models.CharField(blank=True, max_length=100)),
                ("source_channel", models.CharField(choices=[("web", "Web"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("phone", "Phone"), ("email", "Email"), ("crm_import", "CRM Import"), ("api", "API"), ("demo", "Demo")], default="crm_import", max_length=50)),
                ("raw_data", models.JSONField(default=dict)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("linked_customer_id", models.IntegerField(blank=True, null=True)),
            ],
            options={"ordering": ["-imported_at"]},
        ),
    ]
