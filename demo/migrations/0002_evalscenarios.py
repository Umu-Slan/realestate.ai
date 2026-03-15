# Evaluation harness migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("demo", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="demoscenario",
            name="scenario_type",
            field=models.CharField(db_index=True, default="new_lead", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_customer_type",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_support_category",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_route",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_escalation",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_next_action",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="demoscenario",
            name="expected_qualification_hints",
            field=models.JSONField(default=dict),
        ),
        migrations.RemoveField(model_name="demoscenario", name="external_id"),
        migrations.RemoveField(model_name="demoscenario", name="updated_at"),
        migrations.RemoveField(model_name="demoscenario", name="is_active"),
        migrations.CreateModel(
            name="DemoEvalRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("use_llm", models.BooleanField(default=True)),
                ("total_scenarios", models.IntegerField(default=0)),
                ("passed", models.IntegerField(default=0)),
                ("failed", models.IntegerField(default=0)),
                ("metrics", models.JSONField(default=dict)),
                ("summary", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="DemoEvalResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("passed", models.BooleanField(default=False)),
                ("actual_output", models.JSONField(default=dict)),
                ("expected_output", models.JSONField(default=dict)),
                ("failures", models.JSONField(default=list)),
                ("run_time_ms", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="demo.demoevalrun")),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="eval_results", to="demo.demoscenario")),
            ],
            options={"ordering": ["run", "scenario"], "unique_together": {("run", "scenario")}},
        ),
    ]
