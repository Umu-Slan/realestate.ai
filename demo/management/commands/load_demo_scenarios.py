"""
Load demo scenarios from fixtures into DemoScenario model.
Creates eval identity for support/angry/legal scenarios.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from demo.models import DemoScenario
from leads.models import CustomerIdentity, Customer
from core.enums import SourceChannel


class Command(BaseCommand):
    help = "Load demo evaluation scenarios from fixtures"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing scenarios first")

    def handle(self, *args, **options):
        base = Path(__file__).resolve().parent.parent.parent  # demo app root
        fixtures_dir = base / "fixtures"
        path = fixtures_dir / "demo_scenarios.json"

        if not path.exists():
            self.stdout.write(self.style.ERROR(f"Fixture not found: {path}"))
            return

        if options.get("clear"):
            n = DemoScenario.objects.count()
            DemoScenario.objects.all().delete()
            self.stdout.write(f"Cleared {n} scenarios")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        created = 0
        for item in data:
            messages = item.get("messages", [])
            if not isinstance(messages, list):
                messages = []

            obj, was_created = DemoScenario.objects.update_or_create(
                name=item.get("name", ""),
                scenario_type=item.get("scenario_type", "new_lead"),
                defaults={
                    "description": item.get("description", ""),
                    "messages": messages,
                    "expected_customer_type": item.get("expected_customer_type", ""),
                    "expected_intent": item.get("expected_intent", ""),
                    "expected_temperature": item.get("expected_temperature", ""),
                    "expected_support_category": item.get("expected_support_category", ""),
                    "expected_route": item.get("expected_route", ""),
                    "expected_escalation": item.get("expected_escalation", False),
                    "expected_next_action": item.get("expected_next_action", ""),
                    "expected_qualification_hints": item.get("expected_qualification_hints", {}),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(data)} scenarios ({created} new)"))

        # Create eval identity for support scenarios (so orchestration treats as existing customer)
        identity, _ = CustomerIdentity.objects.get_or_create(
            external_id="eval_support_001",
            defaults={"name": "Eval Support Customer", "email": "eval_support@demo.local"},
        )
        Customer.objects.get_or_create(
            identity=identity,
            defaults={"source_channel": SourceChannel.DEMO},
        )
        self.stdout.write("Eval support identity ready (eval_support_001)")
