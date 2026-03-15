# Generated for v0 modular monolith

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("conversations", "0001_initial"),
        ("leads", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer_id", models.IntegerField()),
                ("conversation_id", models.IntegerField(blank=True, null=True)),
                ("message_id", models.IntegerField(blank=True, null=True)),
                ("category", models.CharField(choices=[("after_sale", "After-Sale"), ("warranty", "Warranty"), ("delivery", "Delivery"), ("payment", "Payment"), ("documentation", "Documentation"), ("complaint", "Complaint"), ("general", "General")], max_length=50)),
                ("summary", models.TextField(blank=True)),
                ("status", models.CharField(default="open", max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Escalation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.CharField(blank=True, max_length=255)),
                ("updated_by", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("reason", models.CharField(choices=[("pricing_request", "Pricing Request"), ("complex_inquiry", "Complex Inquiry"), ("complaint", "Complaint"), ("urgent", "Urgent"), ("vip", "VIP"), ("manual", "Manual")], max_length=50)),
                ("status", models.CharField(choices=[("open", "Open"), ("in_progress", "In Progress"), ("resolved", "Resolved"), ("cancelled", "Cancelled")], default="open", max_length=50)),
                ("resolution", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("conversation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="escalations", to="conversations.conversation")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="escalations", to="leads.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
