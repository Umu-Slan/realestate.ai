"""
Sales evaluation runner - run scenarios, score, persist results.
"""
import time
import uuid
from typing import Any

from evaluation.scoring import DimensionScores, compute_all_scores


def run_sales_scenario(scenario, use_llm: bool = True):
    """Run a single sales scenario through orchestration. Returns (actual_output, run_time_ms)."""
    from orchestration.orchestrator import run_orchestration

    messages = getattr(scenario, "messages", None) or []
    user_msgs = [m for m in messages if (m.get("role") or "").lower() == "user"]
    last_user = user_msgs[-1]["content"] if user_msgs else ""
    history = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages[:-1]
        if m.get("content")
    ]

    start = time.perf_counter()
    run = run_orchestration(
        last_user,
        channel="web",
        external_id="sales_eval_anon",
        conversation_history=history if len(history) > 1 else None,
        use_llm=use_llm,
        use_multi_agent=True,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    routing = run.routing or {}
    scoring = run.scoring or {}
    actual = {
        "intent": (run.intent_result or {}).get("primary", ""),
        "qualification": run.qualification or {},
        "journey_stage": run.journey_stage or "",
        "temperature": scoring.get("temperature", ""),
        "routing": {**routing, "recommended_cta": routing.get("recommended_cta") or scoring.get("next_best_action")},
        "scoring": scoring,
        "recommendation_matches": run.recommendation_matches or [],
        "retrieval_sources": getattr(run, "retrieval_sources", []) or [],
        "final_response": run.final_response or "",
        "policy_decision": run.policy_decision or {},
    }
    return actual, elapsed_ms


def run_sales_evaluation(
    use_llm: bool = True,
    save: bool = True,
    *,
    category: str | None = None,
    limit: int | None = None,
):
    """
    Run SalesEvalScenarios, compute 8-dimension scores, optionally persist.
    Returns summary dict with run_id, metrics, results.

    category: optional SalesEvalScenario.category filter (e.g. intent, arabic).
    limit: max scenarios after ordering (for quick CI smoke).
    """
    from evaluation.models import SalesEvalScenario, SalesEvalRun, SalesEvalResult

    qs = SalesEvalScenario.objects.all().order_by("category", "name")
    if category:
        qs = qs.filter(category=category)
    scenarios = list(qs[:limit] if limit else qs)
    if not scenarios:
        return {"error": "No scenarios loaded. Run: python manage.py load_sales_eval_scenarios"}

    run_id = f"sales_eval_{uuid.uuid4().hex[:12]}"
    results = []
    passed = 0
    failed = 0

    # Aggregate metrics
    dim_sums: dict[str, float] = {}
    dim_counts: dict[str, int] = {}
    for key in ["intent", "qualification", "stage", "recommendation", "objection", "next_step", "arabic_naturalness", "repetition"]:
        dim_sums[key] = 0.0
        dim_counts[key] = 0

    for scenario in scenarios:
        try:
            actual, run_time_ms = run_sales_scenario(scenario, use_llm=use_llm)
        except Exception as e:
            actual = {"error": str(e)}
            run_time_ms = 0

        scores, failures = compute_all_scores(scenario, actual)
        p = len(failures) == 0
        if p:
            passed += 1
        else:
            failed += 1

        # Aggregate (repetition: lower is better, so we store 1 - repetition for "goodness")
        for k, v in scores.to_dict().items():
            if k == "repetition":
                dim_sums[k] += 1.0 - v  # Invert: 1-rep = goodness
            else:
                dim_sums[k] += v
            dim_counts[k] += 1

        expected = {
            "intent": getattr(scenario, "expected_intent", ""),
            "qualification": getattr(scenario, "expected_qualification", {}),
            "stage": getattr(scenario, "expected_stage", ""),
            "objection_key": getattr(scenario, "expected_objection_key", ""),
            "next_action": getattr(scenario, "expected_next_action", ""),
        }

        results.append({
            "scenario": scenario,
            "passed": p,
            "scores": scores.to_dict(),
            "actual": actual,
            "expected": expected,
            "failures": failures,
            "run_time_ms": run_time_ms,
        })

    # Compute aggregate metrics
    metrics = {}
    for k in dim_sums:
        n = dim_counts[k]
        metrics[k] = round(dim_sums[k] / n, 3) if n else 0.0
    # For repetition, we stored 1-rep, so metric = avg(1-rep) = 1 - avg(rep)
    if "repetition" in metrics:
        metrics["repetition_rate"] = round(1.0 - metrics["repetition"], 3)
        metrics["repetition_score"] = metrics["repetition"]  # 1-rep as "goodness"
        del metrics["repetition"]

    if save:
        run_obj = SalesEvalRun.objects.create(
            run_id=run_id,
            use_llm=use_llm,
            total_scenarios=len(scenarios),
            passed=passed,
            failed=failed,
            metrics=metrics,
            summary=f"Passed {passed}/{len(scenarios)}",
        )
        for r in results:
            SalesEvalResult.objects.create(
                run=run_obj,
                scenario=r["scenario"],
                passed=r["passed"],
                scores=r["scores"],
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
        "results": [
            {
                "scenario_name": r["scenario"].name,
                "passed": r["passed"],
                "scores": r["scores"],
                "failures": r["failures"],
            }
            for r in results
        ],
    }
