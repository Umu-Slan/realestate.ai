"""
Run demo evaluation - replay all scenarios, compare outputs, save results.
"""
from django.core.management.base import BaseCommand

from demo.eval_runner import run_evaluation


class Command(BaseCommand):
    help = "Run demo evaluation and save results"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-llm",
            action="store_true",
            help="Use rule-based pipeline only (faster, no API calls)",
        )

    def handle(self, *args, **options):
        use_llm = not options.get("no_llm", False)
        self.stdout.write(f"Running evaluation (use_llm={use_llm})...")

        result = run_evaluation(use_llm=use_llm, save=True)

        if "error" in result:
            self.stdout.write(self.style.ERROR(result["error"]))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Run {result['run_id']}: {result['passed']}/{result['total']} passed"
        ))
        m = result.get("metrics", {})
        self.stdout.write(f"  Intent accuracy: {m.get('intent_accuracy', 0):.1%}")
        self.stdout.write(f"  Temperature agreement: {m.get('lead_temperature_agreement', 0):.1%}")
        self.stdout.write(f"  Route accuracy: {m.get('route_accuracy', 0):.1%}")
        self.stdout.write(f"  Safety failures: {m.get('response_safety_failures', 0)}")

        failed = [r for r in result["results"] if not r["passed"]]
        if failed:
            self.stdout.write(self.style.WARNING(f"\nFailed scenarios ({len(failed)}):"))
            for r in failed[:10]:
                self.stdout.write(f"  - {r['scenario'].name}: {r['failures']}")
            if len(failed) > 10:
                self.stdout.write(f"  ... and {len(failed) - 10} more")
