# Ensure default company exists and backfill existing records

from django.db import migrations


def ensure_default(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    Customer = apps.get_model("leads", "Customer")
    Project = apps.get_model("knowledge", "Project")
    Conversation = apps.get_model("conversations", "Conversation")
    if not Company.objects.exists():
        Company.objects.create(
            name="Default Company",
            slug="default",
            support_email="support@example.com",
            tone_settings={"formality": "professional", "default_lang": "ar"},
            default_channel_settings={"enabled_channels": ["web", "whatsapp"], "default_channel": "web"},
            knowledge_namespace="",
        )
    company = Company.objects.order_by("id").first()
    if not company:
        return
    Customer.objects.filter(company_id__isnull=True).update(company_id=company.id)
    Project.objects.filter(company_id__isnull=True).update(company_id=company.id)
    Conversation.objects.filter(company_id__isnull=True).update(company_id=company.id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("leads", "0005_add_company_fk"),
        ("knowledge", "0005_add_company_fk"),
        ("conversations", "0002_add_company_fk"),
    ]

    operations = [
        migrations.RunPython(ensure_default, noop),
    ]
