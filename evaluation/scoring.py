"""
Sales evaluation scoring - deterministic scores for 8 dimensions.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionScores:
    """Per-dimension scores 0-1 (higher is better, except repetition)."""
    intent: float = 0.0
    qualification: float = 0.0
    stage: float = 0.0
    recommendation: float = 0.0
    objection: float = 0.0
    next_step: float = 0.0
    arabic_naturalness: float = 0.0
    repetition: float = 0.0  # 0 = no repetition (good), 1 = high repetition (bad)

    def to_dict(self) -> dict:
        return {
            "intent": round(self.intent, 3),
            "qualification": round(self.qualification, 3),
            "stage": round(self.stage, 3),
            "recommendation": round(self.recommendation, 3),
            "objection": round(self.objection, 3),
            "next_step": round(self.next_step, 3),
            "arabic_naturalness": round(self.arabic_naturalness, 3),
            "repetition": round(self.repetition, 3),
        }


# Intent aliases for fuzzy matching
INTENT_ALIASES = {
    "project_inquiry": ["project_inquiry", "property_purchase", "general_info", "price_inquiry"],
    "property_purchase": ["property_purchase", "project_inquiry", "schedule_visit"],
    "price_inquiry": ["price_inquiry", "project_inquiry"],
    "schedule_visit": ["schedule_visit", "property_purchase", "project_inquiry"],
    "brochure_request": ["brochure_request", "project_inquiry"],
    "installment_inquiry": ["installment_inquiry", "price_inquiry"],
    "investment_inquiry": ["investment_inquiry", "project_inquiry"],
    "location_inquiry": ["location_inquiry", "project_inquiry"],
    "general_info": ["general_info", "other", "project_inquiry"],
}


def _normalize(s: str) -> str:
    return (str(s) if s else "").lower().strip()


def _intent_matches(expected: str, actual: str, aliases: list | None = None) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual)
    if exp == act:
        return True
    check = aliases or INTENT_ALIASES.get(exp, [])
    if act in [a.lower() for a in check]:
        return True
    if exp in INTENT_ALIASES and act in INTENT_ALIASES.get(exp, []):
        return True
    return False


def score_intent(
    actual_intent: str,
    expected_intent: str,
    expected_aliases: list | None = None,
) -> float:
    """Intent accuracy: 1 if match, 0 otherwise."""
    if not expected_intent:
        return 1.0  # No expectation = pass
    return 1.0 if _intent_matches(expected_intent, actual_intent, expected_aliases) else 0.0


def score_qualification_completeness(
    actual_qual: dict,
    expected_qual: dict,
) -> float:
    """Qualification completeness: fraction of expected fields present and roughly correct."""
    if not expected_qual:
        return 1.0

    def _match_budget(actual: dict, key: str, expected_val: Any) -> bool:
        v = actual.get(key)
        if v is None and expected_val is None:
            return True
        if v is None:
            return False
        try:
            return abs(float(v) - float(expected_val)) <= float(expected_val) * 0.2
        except (ValueError, TypeError):
            return str(v) == str(expected_val)

    def _match_str(actual: dict, key: str, expected_val: Any) -> bool:
        v = (actual.get(key) or "").strip().lower()
        exp = (str(expected_val) if expected_val else "").strip().lower()
        if not exp:
            return True
        return exp in v or v in exp

    checks = []
    if "budget_min" in expected_qual:
        checks.append(_match_budget(actual_qual, "budget_min", expected_qual.get("budget_min")))
    if "budget_max" in expected_qual:
        checks.append(_match_budget(actual_qual, "budget_max", expected_qual.get("budget_max")))
    if "location_preference" in expected_qual or "location" in expected_qual:
        loc = expected_qual.get("location_preference") or expected_qual.get("location")
        checks.append(_match_str(actual_qual, "location_preference", loc))
    if "property_type" in expected_qual:
        checks.append(_match_str(actual_qual, "property_type", expected_qual.get("property_type")))

    if not checks:
        return 1.0
    return sum(checks) / len(checks)


def score_stage(actual_stage: str, expected_stage: str) -> float:
    """Stage accuracy: 1 if match (with fuzzy), 0 otherwise."""
    if not expected_stage:
        return 1.0
    act = _normalize(actual_stage)
    exp = _normalize(expected_stage)
    if act == exp:
        return 1.0
    # Fuzzy: consideration/exploration, shortlisting/consideration
    stage_aliases = {
        "consideration": ["consideration", "exploration"],
        "shortlisting": ["shortlisting", "consideration"],
        "visit_planning": ["visit_planning", "negotiation"],
        "awareness": ["awareness", "exploration"],
    }
    for canonical, alts in stage_aliases.items():
        if exp == canonical and act in alts:
            return 0.8  # Partial credit
    return 0.0


def score_recommendation_relevance(
    actual_matches: list,
    actual_qual: dict,
    expected_criteria: dict,
    has_response: bool = True,
) -> float:
    """Recommendation relevance: do we have matches that fit criteria?"""
    if not expected_criteria:
        return 1.0
    if not has_response:
        return 0.0
    if not actual_matches:
        return 0.3  # No matches but we tried
    # Check if any match fits location/budget
    budget_min = expected_criteria.get("budget_min")
    budget_max = expected_criteria.get("budget_max")
    location = (expected_criteria.get("location") or "").lower()

    fits = 0
    for m in actual_matches[:5]:
        pm = m if isinstance(m, dict) else {}
        price_min = pm.get("price_min")
        price_max = pm.get("price_max")
        loc = (pm.get("location") or "").lower()
        if budget_min and price_min and float(price_min) > float(budget_min) * 1.5:
            continue
        if budget_max and price_max and float(price_max) < float(budget_max) * 0.5:
            continue
        if location and loc and location not in loc:
            continue
        fits += 1
    return min(1.0, 0.5 + 0.5 * (fits / max(1, len(actual_matches))))


def score_objection_handling(
    user_message: str,
    actual_response: str,
    expected_objection_key: str,
    used_objection_library: bool = False,
) -> float:
    """Objection handling quality: empathetic, used library, addressed concern."""
    if not expected_objection_key:
        return 1.0  # Not an objection scenario
    score = 0.0
    # Did we respond?
    if actual_response and len(actual_response) > 20:
        score += 0.3
    if actual_response and len(actual_response) > 80:
        score += 0.1
    # Empathy markers in Arabic (incl. consultant tone from objection library)
    empathy_ar = [
        "فهمت",
        "أتفهم",
        "أفهم",
        "نفهم",
        "قلقك",
        "مخاوفك",
        "مشكلتك",
        "طبيعي",
        "سليم",
        "مميزات",
        "أساسي",
        "راحتك",
        "أولويات",
    ]
    empathy_en = ["understand", "concern", "appreciate"]
    resp = (actual_response or "").lower()
    if any(e in resp or e in actual_response for e in empathy_ar + empathy_en):
        score += 0.3
    # Addressed with options (تقسيط، خيارات، فريق)
    options = ["تقسيط", "خيارات", "فريق", "خطط", "installment", "options", "team", "plans"]
    if any(o in resp or o in actual_response for o in options):
        score += 0.2
    if used_objection_library:
        score += 0.2
    return min(1.0, score)


# Expected next_action in fixtures may differ from runtime CTA strings (nurture, clarify_intent, etc.)
_NEXT_ACTION_EQUIVALENTS: dict[str, frozenset[str]] = {
    "ask_budget": frozenset(
        {"ask_budget", "nurture", "clarify_intent", "recommend_project", "recommend_projects", "ask_location"}
    ),
    "ask_location": frozenset(
        {"ask_location", "nurture", "clarify_intent", "recommend_project", "recommend_projects", "ask_budget"}
    ),
    "recommend_projects": frozenset({"recommend_projects", "recommend_project", "nurture", "propose_visit"}),
    "propose_visit": frozenset({"propose_visit", "nurture", "clarify_intent", "address_objection"}),
}


def _next_action_matches_expected(expected: str, actual: str) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual)
    if not exp:
        return True
    if exp == act or exp in act or act in exp:
        return True
    alts = _NEXT_ACTION_EQUIVALENTS.get(exp, frozenset())
    if act in alts:
        return True
    return any(a in act for a in alts if len(a) > 4)


def score_next_step_usefulness(
    actual_response: str,
    routing: dict,
    expected_next_action: str,
) -> float:
    """Next-step usefulness: did we suggest a concrete next action?"""
    if not expected_next_action:
        return 1.0
    resp = (actual_response or "").lower()
    # CTA phrases
    cta_phrases_ar = [
        "بروشور",
        "معاينة",
        "زيارة",
        "تواصل",
        "فريق",
        "اتصل",
        "رابط",
        "متى يناسبك",
        "أي يوم",
        "حجز",
        "منطقة",
        "مساحة",
        "ميزانية",
        "مكالمة",
    ]
    cta_phrases_en = ["brochure", "visit", "call", "team", "contact", "when", "book", "budget", "area"]
    has_cta = any(p in resp or p in (actual_response or "") for p in cta_phrases_ar + cta_phrases_en)
    next_action = (routing or {}).get("recommended_cta") or (routing or {}).get("next_best_action") or ""
    exp = _normalize(expected_next_action)
    act = _normalize(next_action)
    action_match = _next_action_matches_expected(expected_next_action, next_action)
    if has_cta and action_match:
        return 1.0
    if has_cta or action_match:
        return 0.7
    return 0.3


def score_arabic_naturalness(response: str, is_arabic_primary: bool) -> float:
    """Arabic naturalness: heuristics for consultant-like Arabic."""
    if not is_arabic_primary:
        return 1.0
    if not response:
        return 0.0
    text = response.strip()
    # Arabic character ratio
    ar_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    if len(text) < 10:
        return 0.5
    ar_ratio = ar_chars / len(text)
    if ar_ratio < 0.2:
        return 0.3  # Mostly English in Arabic scenario
    # Robotic phrases to penalize
    robotic = [
        "كيف أستطيع مساعدتك", "كيف يمكنني مساعدتك", "مرحباً! كيف",
        "how can i help", "how may i assist",
    ]
    for r in robotic:
        if r.lower() in text.lower():
            return 0.5
    # Natural consultant phrases
    natural = ["أهلاً", "تمام", "يسعدني", "تحت أمرك", "بناءً على", "رشحت", "ميزانية"]
    natural_count = sum(1 for n in natural if n in text)
    base = 0.6 + 0.2 * min(2, natural_count)
    return min(1.0, base + (0.2 if ar_ratio > 0.5 else 0))


def score_repetition(conversation_history: list, current_response: str) -> float:
    """Repetition rate: 0 = no repetition, 1 = high repetition. Lower is better."""
    if not conversation_history or not current_response:
        return 0.0
    assistant_msgs = [
        (m.get("content") or "").strip()
        for m in conversation_history
        if (m.get("role") or "").lower() == "assistant" and m.get("content")
    ]
    if not assistant_msgs:
        return 0.0
    current = (current_response or "").strip().lower()
    # Check for repeated phrases (n-grams)
    words = current.split()
    if len(words) < 4:
        return 0.0
    repeated = 0
    for prev in assistant_msgs[-3:]:  # Last 3 assistant messages
        prev_lower = prev.lower()
        for i in range(0, len(words) - 2):
            ngram = " ".join(words[i : i + 3])
            if len(ngram) > 10 and ngram in prev_lower:
                repeated += 1
    # Normalize to 0-1 (0=no rep, 1=heavy rep)
    max_ngrams = max(1, (len(words) - 2) * 3)  # Approximate
    return min(1.0, repeated / max(2, max_ngrams // 4))


def compute_all_scores(
    scenario: Any,
    actual: dict,
) -> tuple[DimensionScores, list[str]]:
    """Compute all 8 dimension scores and collect failures."""
    failures = []
    scores = DimensionScores()

    # Intent
    exp_intent = getattr(scenario, "expected_intent", None) or ""
    aliases = getattr(scenario, "expected_intent_aliases", None) or []
    scores.intent = score_intent(actual.get("intent", ""), exp_intent, aliases)
    if exp_intent and scores.intent < 1.0:
        failures.append(f"intent: expected {exp_intent}, got {actual.get('intent', '')}")

    # Qualification
    exp_qual = getattr(scenario, "expected_qualification", None) or {}
    scores.qualification = score_qualification_completeness(actual.get("qualification", {}), exp_qual)
    if exp_qual and scores.qualification < 0.8:
        failures.append("qualification: incomplete or incorrect")

    # Stage
    exp_stage = getattr(scenario, "expected_stage", None) or ""
    scores.stage = score_stage(actual.get("journey_stage", ""), exp_stage)
    if exp_stage and scores.stage < 1.0:
        failures.append(f"stage: expected {exp_stage}, got {actual.get('journey_stage', '')}")

    # Recommendation
    exp_criteria = getattr(scenario, "expected_match_criteria", None) or {}
    matches = actual.get("recommendation_matches", []) or actual.get("retrieval_sources", [])
    qual = actual.get("qualification", {})
    scores.recommendation = score_recommendation_relevance(
        matches, qual, exp_criteria, bool(actual.get("final_response"))
    )
    if exp_criteria and scores.recommendation < 0.5:
        failures.append("recommendation: low relevance or missing")

    # Objection
    exp_obj = getattr(scenario, "expected_objection_key", None) or ""
    messages = getattr(scenario, "messages", None) or []
    user_msgs = [m.get("content", "") for m in messages if (m.get("role") or "") == "user"]
    user_msg = user_msgs[-1] if user_msgs else ""
    routing = actual.get("routing", {}) or actual.get("scoring", {})
    used_obj = bool(routing.get("objection_key")) or "objection" in str(actual.get("policy_decision", {}))
    scores.objection = score_objection_handling(
        user_msg, actual.get("final_response", ""), exp_obj, used_obj
    )
    if exp_obj and scores.objection < 0.6:
        failures.append("objection: weak handling")

    # Next step
    exp_next = getattr(scenario, "expected_next_action", None) or ""
    scores.next_step = score_next_step_usefulness(
        actual.get("final_response", ""), routing, exp_next
    )
    if exp_next and scores.next_step < 0.5:
        failures.append(f"next_step: expected {exp_next}")

    # Arabic naturalness
    is_ar = getattr(scenario, "is_arabic_primary", True)
    scores.arabic_naturalness = score_arabic_naturalness(actual.get("final_response", ""), is_ar)
    if is_ar and scores.arabic_naturalness < 0.5:
        failures.append("arabic_naturalness: low")

    # Repetition (converse: 1 - score = goodness)
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages[:-1]]
    scores.repetition = score_repetition(history, actual.get("final_response", ""))
    if scores.repetition > 0.5:
        failures.append(f"repetition: high ({scores.repetition:.2f})")

    # Response contains/excludes
    exp_contains = getattr(scenario, "expected_response_contains", None) or []
    exp_excludes = getattr(scenario, "expected_response_excludes", None) or []
    resp = (actual.get("final_response") or "").lower()
    for c in exp_contains:
        if c and c.lower() not in resp:
            failures.append(f"response_missing: '{c}'")
    for e in exp_excludes:
        if e and e.lower() in resp:
            failures.append(f"response_excludes: '{e}'")

    return scores, failures
