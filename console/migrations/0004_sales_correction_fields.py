# Human correction loop - 3-way quality + sales linkage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0003_add_correction_linkage"),
    ]

    operations = [
        migrations.AddField(
            model_name="responsefeedback",
            name="quality",
            field=models.CharField(blank=True, db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name="responsefeedback",
            name="strategy",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="responsefeedback",
            name="objection_type",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="responsefeedback",
            name="recommendation_quality",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="responsefeedback",
            name="stage_decision",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
    ]
