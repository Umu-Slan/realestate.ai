"""
Evaluation harness for conversation and scoring.
Run sample inputs, compare outputs, measure latency.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class EvalCase:
    external_id: str
    messages: list[dict]
    expected_intent: str | None = None
    expected_tier: str | None = None


def run_eval(
    process_fn: Callable[[str, str], dict],
    cases: list[EvalCase],
) -> list[dict]:
    """
    Run cases through process_fn, return results.
    process_fn(external_id, content) -> {response, ...}
    """
    results = []
    for case in cases:
        for msg in case.messages:
            if msg["role"] != "user":
                continue
            out = process_fn(case.external_id, msg["content"])
            results.append({
                "external_id": case.external_id,
                "input": msg["content"],
                "output": out.get("response", ""),
            })
    return results
