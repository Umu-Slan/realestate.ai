# Structured facts: payment plan, delivery timeline, unit category

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("knowledge", "0003_knowledge_upgrade")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="pricing_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("manual", "Manual"),
                    ("csv_import", "CSV Import"),
                    ("erp", "ERP"),
                    ("crm", "CRM"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="availability_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("manual", "Manual"),
                    ("csv_import", "CSV Import"),
                    ("erp", "ERP"),
                    ("crm", "CRM"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ProjectPaymentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("down_payment_pct_min", models.DecimalField(blank=True, decimal_places=2, help_text="Min down payment percentage (e.g. 10)", max_digits=5, null=True)),
                ("down_payment_pct_max", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("installment_years_min", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("installment_years_max", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("csv_import", "CSV Import"), ("erp", "ERP"), ("crm", "CRM")], default="manual", max_length=20)),
                ("notes", models.CharField(blank=True, max_length=500)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_plans", to="knowledge.project")),
            ],
            options={"ordering": ["project"]},
        ),
        migrations.CreateModel(
            name="ProjectDeliveryTimeline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("phase_name", models.CharField(max_length=255)),
                ("phase_name_ar", models.CharField(blank=True, max_length=255)),
                ("expected_start_date", models.DateField(blank=True, null=True)),
                ("expected_end_date", models.DateField(blank=True, null=True)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("csv_import", "CSV Import"), ("erp", "ERP"), ("crm", "CRM")], default="manual", max_length=20)),
                ("notes", models.CharField(blank=True, max_length=500)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_timelines", to="knowledge.project")),
            ],
            options={"ordering": ["project", "expected_start_date"]},
        ),
        migrations.CreateModel(
            name="ProjectUnitCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category_name", models.CharField(max_length=255)),
                ("category_name_ar", models.CharField(blank=True, max_length=255)),
                ("price_min", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("price_max", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("quantity_available", models.PositiveIntegerField(blank=True, help_text="Optional. For ERP/inventory sync.", null=True)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("csv_import", "CSV Import"), ("erp", "ERP"), ("crm", "CRM")], default="manual", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="unit_categories", to="knowledge.project")),
            ],
            options={"ordering": ["project", "category_name"], "verbose_name_plural": "Project unit categories"},
        ),
    ]
