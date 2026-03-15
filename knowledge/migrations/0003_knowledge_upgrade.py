# Knowledge upgrade: access_level, extended document types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("knowledge", "0002_knowledge_system")]

    operations = [
        migrations.AddField(
            model_name="ingesteddocument",
            name="access_level",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("internal", "Internal"),
                    ("restricted", "Restricted"),
                ],
                default="internal",
                help_text="Public=general use; Internal=staff; Restricted=sensitive",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="ingesteddocument",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("project_brochure", "Project Brochure"),
                    ("project_details", "Project Details"),
                    ("project_pdf", "Project PDF"),
                    ("payment_plan", "Payment Plan"),
                    ("faq", "FAQ"),
                    ("sales_script", "Sales Script"),
                    ("support_sop", "Support SOP"),
                    ("objection_handling", "Objection Handling"),
                    ("company_achievement", "Company Achievement"),
                    ("legal_compliance", "Legal/Compliance"),
                    ("achievement", "Achievement"),
                    ("case_study", "Case Study"),
                    ("delivery_history", "Delivery History"),
                    ("project_metadata_csv", "Project Metadata CSV"),
                    ("credibility", "Credibility"),
                    ("other", "Other"),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="rawdocument",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("project_brochure", "Project Brochure"),
                    ("project_details", "Project Details"),
                    ("project_pdf", "Project PDF"),
                    ("payment_plan", "Payment Plan"),
                    ("faq", "FAQ"),
                    ("sales_script", "Sales Script"),
                    ("support_sop", "Support SOP"),
                    ("objection_handling", "Objection Handling"),
                    ("company_achievement", "Company Achievement"),
                    ("legal_compliance", "Legal/Compliance"),
                    ("achievement", "Achievement"),
                    ("case_study", "Case Study"),
                    ("delivery_history", "Delivery History"),
                    ("project_metadata_csv", "Project Metadata CSV"),
                    ("credibility", "Credibility"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=50,
            ),
        ),
    ]
