"""Onboarding tests: document batch, structured import, batch tracking."""
import csv
import tempfile
from pathlib import Path

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType, OnboardingItemStatus
from onboarding.services import run_document_batch, import_structured_csv
from knowledge.models import IngestedDocument, Project, ProjectPaymentPlan
from companies.models import Company
from core.enums import DocumentType


class OnboardingBatchTest(TestCase):
    """Test OnboardingBatch and OnboardingItem models."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co", slug="test")

    def test_batch_creation(self):
        batch = OnboardingBatch.objects.create(
            company=self.company,
            batch_type=OnboardingBatchType.DOCUMENTS,
            status="completed",
            imported_count=2,
            total_count=2,
        )
        self.assertEqual(batch.imported_count, 2)
        self.assertEqual(batch.summary["imported"], 2)


class StructuredImportTest(TestCase):
    """Test structured CSV import."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co", slug="test")

    def test_import_project_csv(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name", "location", "price_min", "price_max", "installment_years_min", "down_payment_pct_min"])
            w.writeheader()
            w.writerow({
                "name": "Project Alpha",
                "location": "New Cairo",
                "price_min": "1500000",
                "price_max": "3000000",
                "installment_years_min": "5",
                "down_payment_pct_min": "20",
            })
            path = f.name

        batch = import_structured_csv(path, company_id=self.company.id, created_by="test")

        self.assertEqual(batch.imported_count, 1)
        self.assertEqual(batch.batch_type, OnboardingBatchType.STRUCTURED)

        proj = Project.objects.filter(name="Project Alpha", company=self.company).first()
        self.assertIsNotNone(proj)
        self.assertEqual(proj.location, "New Cairo")
        self.assertEqual(float(proj.price_min), 1500000)

        plan = ProjectPaymentPlan.objects.filter(project=proj).first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.installment_years_min, 5)
        self.assertEqual(float(plan.down_payment_pct_min), 20)
