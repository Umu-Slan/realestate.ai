"""
Print demo evaluation report - last run or by run_id.
"""
from django.core.management.base import BaseCommand

from demo.models import DemoEvalRun, DemoEvalResult


class Command(BaseCommand):
    help = "Print demo evaluation report"

    def add_arguments(self, parser):
        parser.add_argument("run_id", nargs="?", help="Run ID (default: latest)")
        parser.add_argument("--failed-only", action="store_true", help="Show only failed scenarios")
        parser.add_argument("--confusion", action="store_true", help="Show confusion areas (intent/temp mismatches)")

    def handle(self, *args, **options):
        run_id = options.get("run_id")
        if run_id:
            run = DemoEvalRun.objects.filter(run_id=run_id).first()
        else:
            run = DemoEvalRun.objects.order_by("-created_at").first()

        if not run:
            self.stdout.write(self.style.ERROR("No evaluation runs found. Run: python manage.py run_demo_eval"))
            return

        self.stdout.write(self.style.SUCCESS(f"Report: {run.run_id}"))
        self.stdout.write(f"  Date: {run.created_at}")
        self.stdout.write(f"  LLM: {run.use_llm}")
        self.stdout.write(f"  Passed: {run.passed}/{run.total_scenarios}")

        m = run.metrics or {}
        self.stdout.write("\nMetrics:")
        self.stdout.write(f"  Intent accuracy: {m.get('intent_accuracy', 0):.1%}")
        self.stdout.write(f"  Lead temperature agreement: {m.get('lead_temperature_agreement', 0):.1%}")
        self.stdout.write(f"  Escalation correctness: {m.get('escalation_correctness', 0):.1%}")
        self.stdout.write(f"  Support category accuracy: {m.get('support_category_accuracy', 0):.1%}")
        self.stdout.write(f"  Route accuracy: {m.get('route_accuracy', 0):.1%}")
        self.stdout.write(f"  Response safety failures: {m.get('response_safety_failures', 0)}")

        results = run.results.all().select_related("scenario")
        if options.get("failed_only"):
            results = results.filter(passed=False)

        if options.get("confusion"):
            self.stdout.write("\nConfusion areas:")
            intent_mismatches = {}
            temp_mismatches = {}
            for res in run.results.filter(passed=False).select_related("scenario"):
                for f in res.failures or []:
                    if "intent:" in f.lower():
                        key = f
                        intent_mismatches[key] = intent_mismatches.get(key, 0) + 1
                    elif "temperature:" in f.lower():
                        key = f
                        temp_mismatches[key] = temp_mismatches.get(key, 0) + 1
            for k, v in sorted(intent_mismatches.items(), key=lambda x: -x[1])[:5]:
                self.stdout.write(f"  Intent: {k} (x{v})")
            for k, v in sorted(temp_mismatches.items(), key=lambda x: -x[1])[:5]:
                self.stdout.write(f"  Temp: {k} (x{v})")
        else:
            self.stdout.write(f"\nResults ({results.count()}):")
            for res in results[:30]:
                status = "PASS" if res.passed else "FAIL"
                style = self.style.SUCCESS if res.passed else self.style.ERROR
                failures = ", ".join(res.failures[:2]) if res.failures else ""
                self.stdout.write(style(f"  [{status}] {res.scenario.name} ({res.scenario.scenario_type}) {failures}"))
            if results.count() > 30:
                self.stdout.write(f"  ... and {results.count() - 30} more")
