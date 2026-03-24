"""
Seed all features with clean demo data for console/admin showcase.
Runs: make_demo_ready, load_demo_data, seed_demo_data, seed_escalations,
      load_demo_users, load_demo_scenarios, load_sales_eval_scenarios,
      plus ImprovementSignal and OnboardingBatch if empty.
Run: python manage.py seed_all_features
     python manage.py seed_all_features --replace   # Clear escalations first
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone


class Command(BaseCommand):
    help = "Fill all features with clean demo data (projects, customers, conversations, escalations, scenarios, improvement, onboarding)"

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Replace escalations with fresh seed")
        parser.add_argument("--skip-migrate", action="store_true", help="Skip migrations in make_demo_ready")

    def handle(self, *args, **options):
        report = []

        # 1. make_demo_ready (projects, customers, CRM leads, admin)
        self.stdout.write("1. make_demo_ready...")
        call_command("make_demo_ready", skip_migrate=options.get("skip_migrate", False), verbosity=1)
        report.append("make_demo_ready: projects, customers, CRM leads, admin user")

        # 2. load_demo_data (conversations from fixtures, snapshots, support, knowledge, corrections)
        self.stdout.write("2. load_demo_data...")
        call_command("load_demo_data", verbosity=1)
        report.append("load_demo_data: conversations, orchestration snapshots, lead data, support, knowledge, corrections")

        # 3. seed_demo_data (extra customers, conversations, recommendations, support)
        self.stdout.write("3. seed_demo_data...")
        call_command("seed_demo_data", verbosity=1)
        report.append("seed_demo_data: 20 customers, 30 conversations, 15 recommendations, 5 support cases")

        # 4. seed_escalations (rich handoff summaries)
        self.stdout.write("4. seed_escalations...")
        if options.get("replace"):
            call_command("seed_escalations", replace=True, verbosity=1)
        else:
            call_command("seed_escalations", verbosity=1)
        report.append("seed_escalations: 6 sample escalations with handoff summaries")

        # 5. load_demo_users
        self.stdout.write("5. load_demo_users...")
        call_command("load_demo_users", verbosity=1)
        report.append("load_demo_users: admin, operator, reviewer, demo (password: demo123!)")

        # 6. load_demo_scenarios
        self.stdout.write("6. load_demo_scenarios...")
        call_command("load_demo_scenarios", clear=True, verbosity=1)
        report.append("load_demo_scenarios: demo eval scenarios (new_lead, hot/warm/cold, support, angry, legal, spam)")

        # 7. load_sales_eval_scenarios
        self.stdout.write("7. load_sales_eval_scenarios...")
        call_command("load_sales_eval_scenarios", clear=True, verbosity=1)
        report.append("load_sales_eval_scenarios: intent, qualification, objection, follow_up, arabic, mixed")

        # 8. ImprovementSignal (if empty)
        self._seed_improvement_signals(report)

        # 9. OnboardingBatch (if empty)
        self._seed_onboarding_batch(report)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("All features seeded successfully!"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        for line in report:
            self.stdout.write(f"  • {line}")
        self.stdout.write("")

    def _seed_improvement_signals(self, report):
        from improvement.models import ImprovementSignal
        from companies.services import get_default_company

        if ImprovementSignal.objects.exists():
            self.stdout.write("8. ImprovementSignal: already has data, skipping")
            return

        company = get_default_company()
        now = timezone.now()
        signals = [
            {"issue_type": "escalation_reason", "source_feature": "support", "pattern_key": "angry_customer", "frequency": 3, "recommended_action": "تحسين مسار الشكاوى والرد السريع"},
            {"issue_type": "support_category", "source_feature": "support", "pattern_key": "delivery", "frequency": 2, "recommended_action": "إضافة FAQ عن مواعيد التسليم"},
            {"issue_type": "objection_type", "source_feature": "sales", "pattern_key": "price_too_high", "frequency": 2, "recommended_action": "تحديث رسائل التقسيط والخصومات"},
            {"issue_type": "low_confidence_recommendation", "source_feature": "recommendation", "pattern_key": "apartment_120m", "frequency": 1, "recommended_action": "مراجعة توصيات الوحدات ١٢٠ متر"},
        ]
        for s in signals:
            ImprovementSignal.objects.create(company=company, **s, last_seen_at=now)
        self.stdout.write(f"8. ImprovementSignal: created {len(signals)} sample signals")
        report.append("ImprovementSignal: 4 sample signals (escalation_reason, support_category, objection_type, low_confidence)")

    def _seed_onboarding_batch(self, report):
        from onboarding.models import OnboardingBatch, OnboardingItem, OnboardingBatchType, OnboardingItemStatus
        from companies.services import get_default_company

        if OnboardingBatch.objects.exists():
            self.stdout.write("9. OnboardingBatch: already has data, skipping")
            return

        company = get_default_company()
        batch = OnboardingBatch.objects.create(
            company=company,
            batch_type=OnboardingBatchType.DOCUMENTS,
            name="Demo batch - initial docs",
            status="completed",
            imported_count=3,
            skipped_count=0,
            failed_count=0,
            stale_count=0,
            total_count=3,
            created_by="demo_seed",
        )
        for i, (name, status) in enumerate([
            ("دليل مشروع النخيل.pdf", OnboardingItemStatus.SUCCESS),
            ("عروض الأسعار.xlsx", OnboardingItemStatus.SUCCESS),
            ("شروط الدفع.docx", OnboardingItemStatus.SUCCESS),
        ]):
            OnboardingItem.objects.create(
                batch=batch,
                item_type="document",
                source_name=name,
                status=status,
                document_id=None,
            )
        self.stdout.write("9. OnboardingBatch: created 1 sample batch with 3 items")
        report.append("OnboardingBatch: 1 sample batch (3 document items)")
