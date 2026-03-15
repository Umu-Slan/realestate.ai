# CRM sync status - track synchronization state for operator visibility

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("crm", "0003_crm_integration_foundation")]

    operations = [
        migrations.AddField(
            model_name="crmrecord",
            name="sync_status",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="internal",
                help_text="internal=local only; pending=pending external push; synced=pushed; failed=push failed",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="sync_error",
            field=models.TextField(blank=True, help_text="Last sync failure message"),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="sync_vendor",
            field=models.CharField(
                blank=True,
                help_text="Target vendor: salesforce, hubspot, etc.",
                max_length=50,
            ),
        ),
    ]
