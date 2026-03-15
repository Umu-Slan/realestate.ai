"""
make_demo_ready: Migrate, seed demo data, create admin user.
Run: python manage.py make_demo_ready
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model

from companies.services import get_default_company
from leads.models import CustomerIdentity, Customer
from knowledge.models import Project
from accounts.models import UserProfile, Role
from crm.models import CRMRecord
from core.enums import CustomerType, SourceChannel


User = get_user_model()


class Command(BaseCommand):
    help = "Migrate, seed demo data, create admin user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-username",
            default="admin",
            help="Admin username (default: admin)",
        )
        parser.add_argument(
            "--admin-email",
            default="admin@demo.local",
            help="Admin email",
        )
        parser.add_argument(
            "--admin-password",
            default="demo123!",
            help="Admin password (default: demo123!)",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Skip migrations",
        )

    def handle(self, *args, **options):
        if not options["skip_migrate"]:
            self.stdout.write("Running migrations...")
            call_command("migrate", verbosity=1)
            self.stdout.write(self.style.SUCCESS("Migrations complete."))

        self.stdout.write("Seeding demo data...")
        self._seed_projects()
        self._seed_customers()
        self._seed_crm_leads()
        self._create_admin(options)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Demo environment ready!"))
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("  1. python manage.py runserver")
        self.stdout.write("  2. Open http://localhost:8000/admin/")
        self.stdout.write("  3. Login: admin / demo123!")
        self.stdout.write("")
        self.stdout.write("Change the admin password in production!")
        self.stdout.write("")

    def _seed_projects(self):
        projects = [
            ("Palm Hills October", "بالم هيلز أكتوبر", "6 October City", 2500000, 12000000, ["apartment", "villa"]),
            ("Sheikh Zayed Residence", "الشيخ زايد ريزيدنس", "Sheikh Zayed", 3000000, 8000000, ["apartment"]),
            ("New Cairo Heights", "نيو القاهرة هايتس", "New Cairo", 4000000, 15000000, ["apartment", "duplex"]),
            ("Fifth Settlement Park", "التجمع الخامس بارك", "Fifth Settlement", 2000000, 6000000, ["apartment"]),
            ("West Town", "وست تاون", "6 October City", 1500000, 5000000, ["apartment", "townhouse"]),
            ("Marina Heights", "مارينا هايتس", "North Coast", 5000000, 25000000, ["apartment", "villa"]),
            ("Madinet Nasr", "مدينة نصر", "Nasr City", 1800000, 4500000, ["apartment"]),
            ("Mivida", "ميفيدا", "New Cairo", 3500000, 18000000, ["apartment", "villa"]),
            ("Zed Sheikh Zayed", "زيد الشيخ زايد", "Sheikh Zayed", 2200000, 7000000, ["apartment"]),
            ("Cairo Festival City", "كايرو فيستيفال سيتي", "New Cairo", 2800000, 9000000, ["apartment", "townhouse"]),
        ]
        company = get_default_company()
        for name, name_ar, location, price_min, price_max, pt in projects:
            Project.objects.get_or_create(
                name=name,
                defaults={
                    "name_ar": name_ar,
                    "location": location,
                    "price_min": price_min,
                    "price_max": price_max,
                    "property_types": pt,
                    "availability_status": "available",
                    "is_active": True,
                    "company": company,
                },
            )
        self.stdout.write("  - 10 projects seeded")

    def _seed_customers(self):
        company = get_default_company()
        first_names = ["أحمد", "محمد", "علي", "خالد", "عمر", "ياسر", "كريم", "سارة", "نور", "مريم", "فاطمة", "هدى", "عبدالله", "يوسف", "إبراهيم", "محمود", "حسن", "أميرة", "رانيا", "دينا", "John", "Michael", "David", "Sarah", "Emma"]
        for i, name in enumerate(first_names):
            ext_id = f"demo_customer_{i+1:03d}"
            identity, _ = CustomerIdentity.objects.get_or_create(
                external_id=ext_id,
                defaults={"name": name, "phone": f"+2010{i:07d}", "email": f"{ext_id}@demo.local"},
            )
            ct = [CustomerType.NEW_LEAD, CustomerType.EXISTING_CUSTOMER, CustomerType.RETURNING_LEAD][i % 3]
            Customer.objects.get_or_create(
                identity=identity,
                company=company,
                defaults={
                    "customer_type": ct,
                    "source_channel": SourceChannel.WEB if i % 2 == 0 else SourceChannel.WHATSAPP,
                    "is_active": True,
                },
            )
        self.stdout.write("  - 25 demo customers seeded")

    def _seed_crm_leads(self):
        import random

        classifications = ["hot", "warm", "cold", "qualified", "unqualified", "converted", "lost"]
        for i in range(100):
            crm_id = f"CRM-{2000 + i:04d}"
            if CRMRecord.objects.filter(crm_id=crm_id).exists():
                continue
            CRMRecord.objects.create(
                crm_id=crm_id,
                external_name=f"Lead {i+1}",
                external_phone=f"+2011{random.randint(1000000, 9999999)}",
                external_email=f"lead{i+1}@example.com",
                historical_classification=random.choice(classifications),
                historical_score=random.randint(0, 100) if random.random() > 0.3 else None,
                source_channel=SourceChannel.CRM_IMPORT,
                raw_data={"import_batch": "demo", "index": i},
            )
        self.stdout.write("  - 100 historical CRM leads seeded")

    def _create_admin(self, options):
        username = options["admin_username"]
        email = options["admin_email"]
        password = options["admin_password"]
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"  - Admin user created: {username} / {password}")
        else:
            self.stdout.write(f"  - Admin user '{username}' already exists")
        UserProfile.objects.get_or_create(user=user, defaults={"role": Role.ADMIN})
