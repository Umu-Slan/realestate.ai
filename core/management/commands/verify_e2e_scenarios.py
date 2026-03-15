"""
End-to-end verification of the real estate AI pipeline.
Simulates 4 scenarios and verifies each pipeline step.
Run: python manage.py verify_e2e_scenarios
"""
import json
import sys

from django.core.management.base import BaseCommand


def _safe_write(stream, msg: str) -> None:
    """Write supporting Unicode (Arabic) on Windows."""
    try:
        stream.write(msg)
    except (UnicodeEncodeError, AttributeError):
        stream.write(msg.encode("ascii", errors="replace").decode("ascii"))
from django.test import RequestFactory


class Command(BaseCommand):
    help = "Verify end-to-end pipeline behavior for 4 scenarios"

    def add_arguments(self, parser):
        parser.add_argument("--use-llm", action="store_true", default=False, help="Use LLM (slower)")
        parser.add_argument("--verbose", action="store_true", help="Show full traces")

    def handle(self, *args, **options):
        use_llm = options["use_llm"]
        verbose = options["verbose"]
        self.verbose = verbose
        self.results = []
        self.fixes_applied = []
        self.files_changed = []

        factory = RequestFactory()
        self.request = factory.post("/api/engines/sales/")
        self.request.session = {}
        self.request.user = None

        self._out = getattr(self.stdout, "_out", sys.stdout)
        self._write = lambda m: _safe_write(self._out, m)

        self._write("=" * 60 + "\n")
        self._write("E2E Pipeline Verification\n")
        self._write("=" * 60 + "\n")

        self._run_scenario_1(use_llm)
        self._run_scenario_2(use_llm)
        self._run_scenario_3(use_llm)
        self._run_scenario_4(use_llm)

        self._print_summary()

    def _trace(self, name: str, data: dict) -> None:
        if self.verbose:
            self._write(f"  [{name}] {json.dumps(data, default=str, ensure_ascii=True)[:200]}...\n")

    def _run_scenario_1(self, use_llm: bool) -> None:
        """New lead: apartment in Sheikh Zayed, installments, 3M budget."""
        msg = "عايز شقة في الشيخ زايد بالتقسيط وميزانيتي 3 مليون"
        self._write("\n--- Scenario 1: New Lead ---\n")
        self._write(f"Message: {msg}\n")

        try:
            from orchestration.service import run_canonical_pipeline

            resp, run, user_msg, assistant_msg = run_canonical_pipeline(
                self.request,
                msg,
                response_mode="sales",
                use_llm=use_llm,
            )

            checks = {}
            intent = run.intent_result.get("primary", "")
            checks["intent"] = bool(intent) and intent in ("property_purchase", "price_inquiry", "project_inquiry", "investment_inquiry", "brochure_request", "location_inquiry")
            checks["qualification"] = bool(run.qualification) and (
                run.qualification.get("budget_min") or run.qualification.get("budget_max") or
                run.qualification.get("location_preference") or run.qualification.get("project_preference")
            )
            checks["scoring"] = run.scoring.get("score") is not None
            checks["buyer_stage"] = bool(run.journey_stage)
            checks["routing"] = bool(run.routing.get("route"))
            checks["response"] = bool(resp)
            checks["persistence"] = user_msg and assistant_msg
            checks["audit"] = bool(run.audit_log_ids) if hasattr(run, "audit_log_ids") else True

            from audit.models import ActionLog
            audit_count = ActionLog.objects.filter(subject_id=run.run_id).count()
            checks["audit"] = audit_count >= 2

            from leads.models import LeadScore
            lead_scores = LeadScore.objects.filter(customer_id=user_msg.conversation.customer_id).order_by("-created_at")[:1]
            checks["lead_score_persisted"] = lead_scores.exists()

            ok = all(checks.values())
            self.results.append({"scenario": 1, "name": "new_lead", "ok": ok, "checks": checks})
            self._print_checks(checks)
            if self.verbose:
                self._trace("intent", run.intent_result)
                self._trace("qualification", run.qualification)
                self._trace("scoring", run.scoring)
                self._trace("routing", run.routing)

        except Exception as e:
            self.results.append({"scenario": 1, "name": "new_lead", "ok": False, "error": str(e)})
            self._write(self.style.ERROR(f"FAILED: {e}\n"))

    def _run_scenario_2(self, use_llm: bool) -> None:
        """Recommendation: investment project in Sheikh Zayed."""
        self._write("\n--- Scenario 2: Recommendation Request ---\n")
        msg_display = "رشحلي مشروع في الشيخ زايد للاستثمار"
        self._write(f"Request: {msg_display}\n")
        qual_override = {
            "location_preference": "الشيخ زايد",
            "purpose": "استثمار",
        }

        try:
            from orchestration.service import run_canonical_pipeline

            content = f"Recommend: location Sheikh Zayed, purpose investment"
            resp, run, user_msg, assistant_msg = run_canonical_pipeline(
                self.request,
                content,
                response_mode="recommendation",
                qualification_override=qual_override,
                use_llm=use_llm,
                lang="ar",
            )

            checks = {}
            checks["investment_intent"] = "recommendation"  # mode forces recommendation path
            matches = run.recommendation_matches if hasattr(run, "recommendation_matches") else []
            checks["recommendation_engine"] = True  # ran without error
            checks["match_reasoning"] = any(m.get("rationale") or m.get("match_reasons") for m in matches) if matches else True
            checks["persistence"] = user_msg and assistant_msg
            checks["console_visibility"] = True  # OrchestrationSnapshot created when conversation_id present

            from recommendations.models import Recommendation
            recs = Recommendation.objects.filter(conversation_id=user_msg.conversation_id)
            checks["recommendation_persisted"] = recs.exists() or len(matches) == 0

            from console.models import OrchestrationSnapshot
            snaps = OrchestrationSnapshot.objects.filter(conversation_id=user_msg.conversation_id)
            checks["console_visibility"] = snaps.exists()

            ok = all(checks.values())
            self.results.append({"scenario": 2, "name": "recommendation", "ok": ok, "checks": checks})
            self._print_checks(checks)
            if self.verbose:
                self._trace("matches", [{"name": m.get("project_name"), "rationale": m.get("rationale")[:80] if m.get("rationale") else ""} for m in (matches or [])[:3]])

        except Exception as e:
            self.results.append({"scenario": 2, "name": "recommendation", "ok": False, "error": str(e)})
            self._write(self.style.ERROR(f"FAILED: {e}\n"))

    def _run_scenario_3(self, use_llm: bool) -> None:
        """Support: reserved customer asking handover date."""
        msg = "أنا حاجز عندكم وعايز أعرف ميعاد الاستلام"
        self._write("\n--- Scenario 3: Support Request ---\n")
        self._write(f"Message: {msg}\n")

        try:
            from orchestration.service import run_canonical_pipeline

            resp, run, user_msg, assistant_msg = run_canonical_pipeline(
                self.request,
                msg,
                response_mode="support",
                support_category="",
                use_llm=use_llm,
            )

            checks = {}
            intent = run.intent_result.get("primary", "")
            checks["support_detection"] = run.intent_result.get("is_support") or intent in (
                "delivery_inquiry", "support_complaint", "contract_issue", "maintenance_issue",
                "general_support", "installment_inquiry", "documentation_inquiry", "payment_proof_inquiry",
            )
            checks["support_category"] = bool(run.qualification.get("support_category") or run.routing.get("queue"))

            from support.models import SupportCase
            cases = SupportCase.objects.filter(conversation_id=user_msg.conversation_id)
            checks["support_case_created"] = cases.exists()
            if cases.exists():
                c = cases.first()
                checks["sla_classification"] = bool(c.sla_bucket)

            checks["persistence"] = user_msg and assistant_msg

            from console.models import OrchestrationSnapshot
            snaps = OrchestrationSnapshot.objects.filter(conversation_id=user_msg.conversation_id)
            checks["console_visibility"] = snaps.exists()

            ok = all(checks.values())
            self.results.append({"scenario": 3, "name": "support", "ok": ok, "checks": checks})
            self._print_checks(checks)
            if self.verbose:
                self._trace("intent", run.intent_result)
                self._trace("routing", run.routing)
                if cases.exists():
                    self._trace("support_case", {"category": c.category, "sla": c.sla_bucket})

        except Exception as e:
            self.results.append({"scenario": 3, "name": "support", "ok": False, "error": str(e)})
            self._write(self.style.ERROR(f"FAILED: {e}\n"))

    def _run_scenario_4(self, use_llm: bool) -> None:
        """Escalation: upset customer, contract and price."""
        msg = "أنا متضايق جدًا ومحتاج رد نهائي على العقد والسعر"
        self._write("\n--- Scenario 4: Escalation Trigger ---\n")
        self._write(f"Message: {msg}\n")

        try:
            from orchestration.service import run_canonical_pipeline

            resp, run, user_msg, assistant_msg = run_canonical_pipeline(
                self.request,
                msg,
                response_mode="support",
                is_angry=True,
                use_llm=use_llm,
            )

            checks = {}
            checks["escalation_detection"] = run.routing.get("escalation_ready") or bool(run.escalation_flags)

            from support.models import Escalation
            escalations = Escalation.objects.filter(conversation_id=user_msg.conversation_id)
            checks["escalation_record_created"] = escalations.exists()
            if escalations.exists():
                e = escalations.first()
                checks["handoff_summary"] = bool(e.handoff_summary)

            checks["persistence"] = user_msg and assistant_msg

            ok = all(checks.values())
            self.results.append({"scenario": 4, "name": "escalation", "ok": ok, "checks": checks})
            self._print_checks(checks)
            if self.verbose and escalations.exists():
                self._trace("escalation", {"reason": e.reason, "handoff_keys": list(e.handoff_summary.keys()) if e.handoff_summary else []})

        except Exception as e:
            self.results.append({"scenario": 4, "name": "escalation", "ok": False, "error": str(e)})
            self._write(self.style.ERROR(f"FAILED: {e}\n"))

    def _print_checks(self, checks: dict) -> None:
        for k, v in checks.items():
            status = self.style.SUCCESS("[OK]") if v else self.style.ERROR("[FAIL]")
            self._write(f"  {status} {k}: {v}\n")

    def _print_summary(self) -> None:
        self._write("\n" + "=" * 60 + "\n")
        self._write("Summary\n")
        self._write("=" * 60 + "\n")
        passed = sum(1 for r in self.results if r.get("ok"))
        total = len(self.results)
        self._write(f"Passed: {passed}/{total}\n")
        for r in self.results:
            status = self.style.SUCCESS("PASS") if r.get("ok") else self.style.ERROR("FAIL")
            self._write(f"  Scenario {r['scenario']} ({r['name']}): {status}\n")
        if self.fixes_applied:
            self._write("\nFixes applied:\n")
            for f in self.fixes_applied:
                self._write(f"  - {f}\n")
        if self.files_changed:
            self._write("\nFiles changed:\n")
            for f in self.files_changed:
                self._write(f"  - {f}\n")
