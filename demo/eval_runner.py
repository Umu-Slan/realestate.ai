"""
Evaluation runner - replay scenarios, compare actual vs expected, compute metrics.
"""
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from demo.models import DemoScenario, DemoEvalRun, DemoEvalResult


# Intent aliases for fuzzy matching (actual may use different label)
INTENT_ALIASES = {
    "project_inquiry": ["project_inquiry", "property_purchase", "general_info", "price_inquiry"],
    "property_purchase": ["property_purchase", "project_inquiry", "schedule_visit"],
    "price_inquiry": ["price_inquiry", "project_inquiry"],
    "schedule_visit": ["schedule_visit", "property_purchase"],
    "brochure_request": ["brochure_request", "project_inquiry"],
    "installment_inquiry": ["installment_inquiry", "price_inquiry"],
    "investment_inquiry": ["investment_inquiry", "project_inquiry"],
    "location_inquiry": ["location_inquiry", "project_inquiry"],
    "general_info": ["general_info", "other", "project_inquiry"],
    "support_complaint": ["support_complaint", "complaint", "general_support"],
    "contract_issue": ["contract_issue", "general_support"],
    "maintenance_issue": ["maintenance_issue", "general_support"],
    "delivery_inquiry": ["delivery_inquiry", "general_support"],
    "general_support": ["general_support", "other"],
    "spam": ["spam"],
    "broker_inquiry": ["broker_inquiry"],
    "availability": ["availability", "project_inquiry"],
}

# Route aliases
ROUTE_ALIASES = {
    "sales": ["sales", "senior_sales", "default"],
    "support": ["support", "support_escalation", "legal_handoff"],
    "quarantine": ["quarantine"],
    "broker": ["broker"],
    "clarification": ["clarification"],
}


def _normalize(s: str) -> str:
    return (s or "").lower().strip()


def _intent_matches(expected: str, actual: str) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual)
    if exp == act:
        return True
    if exp in INTENT_ALIASES and act in INTENT_ALIASES.get(exp, []):
        return True
    if act in INTENT_ALIASES and exp in INTENT_ALIASES.get(act, []):
        return True
    return False


def _route_matches(expected: str, actual: str) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual or "")
    if exp == act:
        return True
    if exp in ROUTE_ALIASES and act in ROUTE_ALIASES.get(exp, []):
        return True
    if exp in ("support",) and "support" in act:
        return True
    if exp in ("support",) and "legal" in act:
        return True
    return False


def _temperature_matches(expected: str, actual: str) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual or "")
    if not exp:
        return True
    return exp == act


def run_scenario(scenario: DemoScenario, use_llm: bool = True) -> tuple[dict, list[str], int]:
    """
    Run a single scenario through orchestration. Returns (actual_output, failures, run_time_ms).
    """
    from orchestration.orchestrator import run_orchestration

    messages = scenario.messages or []
    user_msgs = [m for m in messages if m.get("role") == "user"]
    last_user = user_msgs[-1]["content"] if user_msgs else ""
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages[:-1] if m.get("content")]

    # Support/angry/legal scenarios: use pre-created identity so we're treated as existing customer
    external_id = "eval_anon"
    if scenario.scenario_type in ("support_case", "angry_customer", "legal_case"):
        external_id = "eval_support_001"

    start = time.perf_counter()
    run = run_orchestration(
        last_user,
        channel="whatsapp",
        external_id=external_id,
        conversation_history=history if len(history) > 1 else None,
        use_llm=use_llm,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    actual = {
        "customer_type": run.routing.get("customer_type", ""),
        "intent": run.intent_result.get("primary", ""),
        "temperature": run.scoring.get("temperature", ""),
        "support_category": run.qualification.get("support_category", ""),
        "route": run.routing.get("route", ""),
        "escalation": bool(run.escalation_flags) or run.routing.get("escalation_ready") or run.policy_decision.get("force_escalation"),
        "next_action": run.scoring.get("next_best_action", ""),
        "qualification": run.qualification,
        "final_response": run.final_response,
        "policy_decision": run.policy_decision,
        "retrieval_sources": run.retrieval_sources,
    }

    failures = []
    exp_ct = _normalize(scenario.expected_customer_type)
    act_ct = _normalize(actual["customer_type"])
    if exp_ct and act_ct and exp_ct != act_ct:
        # Allow new_lead/returning_lead flexibility for ambiguous
        if not (exp_ct in ("new_lead", "returning_lead") and act_ct in ("new_lead", "returning_lead")):
            failures.append(f"customer_type: expected {exp_ct}, got {act_ct}")

    if scenario.expected_intent and not _intent_matches(scenario.expected_intent, actual["intent"]):
        failures.append(f"intent: expected {scenario.expected_intent}, got {actual['intent']}")

    if scenario.expected_temperature and not _temperature_matches(scenario.expected_temperature, actual["temperature"]):
        failures.append(f"temperature: expected {scenario.expected_temperature}, got {actual['temperature']}")

    if scenario.expected_support_category and scenario.scenario_type in ("support_case", "angry_customer", "legal_case"):
        exp_sc = _normalize(scenario.expected_support_category)
        act_sc = _normalize(actual["support_category"])
        if exp_sc and act_sc and exp_sc != act_sc:
            failures.append(f"support_category: expected {exp_sc}, got {act_sc}")

    if scenario.expected_route and not _route_matches(scenario.expected_route, actual["route"]):
        failures.append(f"route: expected {scenario.expected_route}, got {actual['route']}")

    exp_esc = scenario.expected_escalation
    act_esc = actual["escalation"]
    if exp_esc != act_esc:
        failures.append(f"escalation: expected {exp_esc}, got {act_esc}")

    return actual, failures, elapsed_ms


def run_evaluation(use_llm: bool = True, save: bool = True) -> dict:
    """
    Run all DemoScenarios, compare outputs, compute metrics. Returns summary dict.
    """
    scenarios = list(DemoScenario.objects.all())
    if not scenarios:
        return {"error": "No scenarios loaded. Run: python manage.py load_demo_scenarios"}

    run_id = f"eval_{uuid.uuid4().hex[:12]}"
    results = []
    passed = 0
    failed = 0

    # Per-metric counts
    intent_correct = 0
    intent_total = 0
    temp_correct = 0
    temp_total = 0
    escalation_correct = 0
    escalation_total = 0
    support_cat_correct = 0
    support_cat_total = 0
    route_correct = 0
    route_total = 0
    safety_failures = 0

    for scenario in scenarios:
        try:
            actual, failures, run_time_ms = run_scenario(scenario, use_llm=use_llm)
        except Exception as e:
            actual = {"error": str(e)}
            failures = [f"exception: {e}"]
            run_time_ms = 0

        p = len(failures) == 0
        if p:
            passed += 1
        else:
            failed += 1

        # Metrics
        if scenario.expected_intent:
            intent_total += 1
            if _intent_matches(scenario.expected_intent, actual.get("intent", "")):
                intent_correct += 1
        if scenario.expected_temperature:
            temp_total += 1
            if _temperature_matches(scenario.expected_temperature, actual.get("temperature", "")):
                temp_correct += 1
        if scenario.scenario_type in ("support_case", "angry_customer", "legal_case"):
            if scenario.expected_escalation is not None:
                escalation_total += 1
                if scenario.expected_escalation == actual.get("escalation", False):
                    escalation_correct += 1
            if scenario.expected_support_category:
                support_cat_total += 1
                if _normalize(scenario.expected_support_category) == _normalize(actual.get("support_category", "")):
                    support_cat_correct += 1
        if scenario.expected_route:
            route_total += 1
            if _route_matches(scenario.expected_route, actual.get("route", "")):
                route_correct += 1

        if actual.get("policy_decision", {}).get("violations"):
            safety_failures += 1

        expected_out = {
            "customer_type": scenario.expected_customer_type,
            "intent": scenario.expected_intent,
            "temperature": scenario.expected_temperature,
            "support_category": scenario.expected_support_category,
            "route": scenario.expected_route,
            "escalation": scenario.expected_escalation,
        }

        results.append({
            "scenario": scenario,
            "passed": p,
            "actual": actual,
            "expected": expected_out,
            "failures": failures,
            "run_time_ms": run_time_ms,
        })

    metrics = {
        "intent_accuracy": intent_correct / intent_total if intent_total else 0,
        "lead_temperature_agreement": temp_correct / temp_total if temp_total else 0,
        "escalation_correctness": escalation_correct / escalation_total if escalation_total else 0,
        "support_category_accuracy": support_cat_correct / support_cat_total if support_cat_total else 0,
        "route_accuracy": route_correct / route_total if route_total else 0,
        "response_safety_failures": safety_failures,
        "retrieval_usage_count": sum(1 for r in results if r["actual"].get("qualification")),
    }

    if save:
        run_obj = DemoEvalRun.objects.create(
            run_id=run_id,
            use_llm=use_llm,
            total_scenarios=len(scenarios),
            passed=passed,
            failed=failed,
            metrics=metrics,
            summary=f"Passed {passed}/{len(scenarios)}",
        )
        for r in results:
            DemoEvalResult.objects.create(
                run=run_obj,
                scenario=r["scenario"],
                passed=r["passed"],
                actual_output=r["actual"],
                expected_output=r["expected"],
                failures=r["failures"],
                run_time_ms=r["run_time_ms"],
            )

    return {
        "run_id": run_id,
        "total": len(scenarios),
        "passed": passed,
        "failed": failed,
        "metrics": metrics,
        "results": results,
    }
