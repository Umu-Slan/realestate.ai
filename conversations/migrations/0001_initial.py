# Generated for v0 modular monolith

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("leads", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("channel", models.CharField(choices=[("web", "Web"), ("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("phone", "Phone"), ("email", "Email"), ("crm_import", "CRM Import"), ("api", "API"), ("demo", "Demo")], default="web", max_length=50)),
                ("status", models.CharField(choices=[("active", "Active"), ("closed", "Closed"), ("archived", "Archived")], default="active", max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("summary", models.TextField(blank=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversations", to="leads.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(max_length=20)),
                ("content", models.TextField()),
                ("language", models.CharField(blank=True, max_length=10)),
                ("intent", models.CharField(blank=True, choices=[("project_inquiry", "Project Inquiry"), ("pricing", "Pricing"), ("availability", "Availability"), ("schedule_visit", "Schedule Visit"), ("support", "Support"), ("general_info", "General Info"), ("spam", "Spam"), ("other", "Other")], max_length=50)),
                ("intent_confidence", models.CharField(blank=True, choices=[("high", "High"), ("medium", "Medium"), ("low", "Low"), ("unknown", "Unknown")], max_length=20)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="conversations.conversation")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
