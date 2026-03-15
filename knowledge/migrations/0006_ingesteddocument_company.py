# Add company FK to IngestedDocument for company-level docs

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("knowledge", "0005_add_company_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingesteddocument",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ingested_documents",
                to="companies.company",
                db_index=True,
                help_text="Company for company-level docs (SOPs, credibility); project inherits from company if set.",
            ),
        ),
    ]
