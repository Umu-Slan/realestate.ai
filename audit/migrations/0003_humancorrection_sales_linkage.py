# Sales linkage for HumanCorrection - strategy, objection, recommendation, stage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_add_correction_linkage"),
    ]

    operations = [
        migrations.AddField(
            model_name="humancorrection",
            name="sales_linkage",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
