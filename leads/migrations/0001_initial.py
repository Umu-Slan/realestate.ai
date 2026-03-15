# Generated for v0 modular monolith

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CustomerIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("external_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("phone", models.CharField(blank=True, db_index=True, max_length=50)),
                ("email", models.CharField(blank=True, db_index=True, max_length=255)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("merged_into", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="merges", to="leads.customeridentity")),
            ],
            options={"verbose_name_plural": "Customer Identities"},
        ),
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.CharField(blank=True, max_length=255)),
                ("updated_by", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("customer_type", models.CharField(choices=[("new_lead", "New Lead"), ("existing_customer", "Existing Customer"), ("returning_lead", "Returning Lead"), ("broker", "Broker"), ("spam", "Spam"), ("support_customer", "Support Customer")], default="new_lead", max_length=50)),
                ("source_channel", models.CharField(choices=[("web", "Web"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("phone", "Phone"), ("email", "Email"), ("crm_import", "CRM Import"), ("api", "API"), ("demo", "Demo")], default="web", max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("lifecycle_notes", models.TextField(blank=True)),
                ("identity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="customers", to="leads.customeridentity")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LeadProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_channel", models.CharField(choices=[("web", "Web"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("phone", "Phone"), ("email", "Email"), ("crm_import", "CRM Import"), ("api", "API"), ("demo", "Demo")], default="web", max_length=50)),
                ("project_interest", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_profiles", to="leads.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LeadQualification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation_id", models.IntegerField(blank=True, null=True)),
                ("message_id", models.IntegerField(blank=True, null=True)),
                ("version", models.IntegerField(default=1)),
                ("budget_min", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("budget_max", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("property_type", models.CharField(blank=True, max_length=100)),
                ("location_preference", models.CharField(blank=True, max_length=255)),
                ("timeline", models.CharField(blank=True, max_length=100)),
                ("unit_size_sqm", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("raw_extraction", models.JSONField(default=dict)),
                ("confidence", models.CharField(choices=[("high", "High"), ("medium", "Medium"), ("low", "Low"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="qualifications", to="leads.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LeadScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("score", models.IntegerField()),
                ("temperature", models.CharField(choices=[("hot", "Hot"), ("warm", "Warm"), ("cold", "Cold")], max_length=20)),
                ("journey_stage", models.CharField(choices=[("awareness", "Awareness"), ("consideration", "Consideration"), ("decision", "Decision"), ("purchase", "Purchase"), ("post_purchase", "Post-Purchase"), ("unknown", "Unknown")], default="unknown", max_length=50)),
                ("explanation", models.JSONField(default=list)),
                ("rule_version", models.CharField(default="v1", max_length=50)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scores", to="leads.customer")),
                ("lead_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scores", to="leads.leadprofile")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
