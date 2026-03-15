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

    def handle(self, *args, **options):
        use_llm = not options.get("no_llm", False)
        save = not options.get("no_save", False)
        out = run_sales_evaluation(use_llm=use_llm, save=save)
        if out.get("error"):
            self.stdout.write(self.style.ERROR(out["error"]))
            return
        self.stdout.write(self.style.SUCCESS(f"Run {out['run_id']}: {out['passed']}/{out['total']} passed"))
        for k, v in out.get("metrics", {}).items():
            self.stdout.write(f"  {k}: {v}")
        if not save:
            self.stdout.write("(Results not persisted; use without --no-save to save)")
