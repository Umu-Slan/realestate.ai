"""
Load sales evaluation scenarios from fixtures.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from evaluation.models import SalesEvalScenario


class Command(BaseCommand):
    help = "Load sales evaluation scenarios from fixtures"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing scenarios first")

    def handle(self, *args, **options):
        base = Path(__file__).resolve().parent.parent.parent
        fixtures_dir = base / "fixtures"
        path = fixtures_dir / "sales_eval_scenarios.json"

        if not path.exists():
            self.stdout.write(self.style.ERROR(f"Fixture not found: {path}"))
            return

        if options.get("clear"):
            n = SalesEvalScenario.objects.count()
            SalesEvalScenario.objects.all().delete()
            self.stdout.write(f"Cleared {n} scenarios")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        created = 0
        for item in data:
            messages = item.get("messages", [])
            if not isinstance(messages, list):
                messages = []

            obj, was_created = SalesEvalScenario.objects.update_or_create(
                name=item.get("name", ""),
                defaults={
                    "category": item.get("category", "mixed"),
                    "description": item.get("description", ""),
                    "messages": messages,
                    "expected_intent": item.get("expected_intent", ""),
                    "expected_intent_aliases": item.get("expected_intent_aliases", []),
                    "expected_qualification": item.get("expected_qualification", {}),
                    "expected_stage": item.get("expected_stage", ""),
                    "expected_objection_key": item.get("expected_objection_key", ""),
                    "expected_next_action": item.get("expected_next_action", ""),
                    "expected_response_contains": item.get("expected_response_contains", []),
                    "expected_response_excludes": item.get("expected_response_excludes", []),
                    "is_arabic_primary": item.get("is_arabic_primary", True),
                    "expected_match_criteria": item.get("expected_match_criteria", {}),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(data)} scenarios ({created} new)"))
