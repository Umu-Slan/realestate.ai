# CRM extended fields and CRMImportBatch

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("crm", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="crmrecord",
            name="external_username",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="source",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="campaign",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="project_interest",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="status",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="crm_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="crm_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crmrecord",
            name="import_batch_id",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.CreateModel(
            name="CRMImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("file_name", models.CharField(blank=True, max_length=255)),
                ("total_rows", models.IntegerField(default=0)),
                ("imported_count", models.IntegerField(default=0)),
                ("duplicate_count", models.IntegerField(default=0)),
                ("conflict_count", models.IntegerField(default=0)),
                ("error_count", models.IntegerField(default=0)),
                ("status", models.CharField(default="completed", max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
