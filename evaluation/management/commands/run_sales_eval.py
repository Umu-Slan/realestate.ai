"""
Run sales evaluation harness.
"""
from django.core.management.base import BaseCommand

from evaluation.sales_eval_runner import run_sales_evaluation


class Command(BaseCommand):
    help = "Run sales evaluation across all SalesEvalScenarios"

    def add_arguments(self, parser):
        parser.add_argument("--no-llm", action="store_true", help="Use rule-based only (faster)")
        parser.add_argument("--no-save", action="store_true", help="Do not persist results")
        parser.add_argument(
            "--category",
            type=str,
            default=None,
            help="Filter by SalesEvalScenario.category (e.g. intent, arabic, objection)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max scenarios to run after ordering (smoke / quick checks)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print failing scenario names and failure reasons",
        )

    def handle(self, *args, **options):
        use_llm = not options.get("no_llm", False)
        save = not options.get("no_save", False)
        category = options.get("category")
        limit = options.get("limit")
        out = run_sales_evaluation(
            use_llm=use_llm,
            save=save,
            category=category,
            limit=limit,
        )
        if out.get("error"):
            self.stdout.write(self.style.ERROR(out["error"]))
            return
        self.stdout.write(self.style.SUCCESS(f"Run {out['run_id']}: {out['passed']}/{out['total']} passed"))
        if options.get("verbose"):
            for r in out.get("results", []):
                if not r.get("passed"):
                    self.stdout.write(self.style.WARNING(f"  FAIL {r['scenario_name']}: {r.get('failures', [])}"))
        for k, v in out.get("metrics", {}).items():
            self.stdout.write(f"  {k}: {v}")
        if not save:
            self.stdout.write("(Results not persisted; use without --no-save to save)")
